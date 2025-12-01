"""
Issue Fixer - Fix validation issues using LLM with smart analysis.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_client import LLMClient


logger = logging.getLogger(__name__)


# Regex patterns for detection
GAME_TAG_PATTERN = re.compile(r'<[^>]+\|[^>]+>')  # <Name|123|#C|456>
GAME_CODE_PATTERN = re.compile(r'#[YyEeCcRrGgBbWw]|{\d+[^}]*}')  # #Y, #E, {0}, {1:.1f}
BRACKET_PLACEHOLDER = re.compile(r'\[[^\]]+\]')  # [Something]


@dataclass
class BrokenStringIssue:
    """Detected broken string issue."""
    
    issue_type: str
    severity: str  # "critical", "warning", "info"
    description: str
    
    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.issue_type}: {self.description}"


@dataclass
class BrokenStringDetector:
    """Detect various types of broken/corrupted translations."""
    
    # Thresholds
    min_length_ratio: float = 0.3  # Translation should be at least 30% of original length
    max_length_ratio: float = 3.0  # Translation shouldn't be 3x longer than original
    max_latin_ratio: float = 0.4   # Max 40% Latin chars (outside tags) for Russian text
    
    # Character sets
    CYRILLIC = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
    LATIN = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    
    def detect_issues(self, original: str, translated: str) -> list[BrokenStringIssue]:
        """Detect all issues in a translation."""
        issues = []
        
        if not translated or not translated.strip():
            issues.append(BrokenStringIssue(
                "empty_translation",
                "critical",
                "Translation is empty"
            ))
            return issues
        
        # Check for error markers (already handled elsewhere, but include for completeness)
        if self._has_error_markers(translated):
            issues.append(BrokenStringIssue(
                "error_marker",
                "critical",
                "Contains error marker like [MISSING] or [PARSE ERROR]"
            ))
        
        # Check for JSON artifacts
        if json_issue := self._check_json_artifacts(translated):
            issues.append(json_issue)
        
        # Check for encoding issues
        if encoding_issue := self._check_encoding(translated):
            issues.append(encoding_issue)
        
        # Check for truncation (only if original is substantial)
        if len(original) > 20:
            if truncation_issue := self._check_truncation(original, translated):
                issues.append(truncation_issue)
        
        # Check for untranslated text (too much Latin)
        if len(original) > 10:
            if latin_issue := self._check_untranslated(original, translated):
                issues.append(latin_issue)
        
        # Check for repetition
        if repetition_issue := self._check_repetition(translated):
            issues.append(repetition_issue)
        
        # Check for incomplete sentences
        if incomplete_issue := self._check_incomplete(original, translated):
            issues.append(incomplete_issue)
        
        return issues
    
    def _has_error_markers(self, text: str) -> bool:
        """Check for error markers."""
        markers = ["[MISSING]", "[PARSE ERROR]", "[ERROR]", "[INCOMPLETE]"]
        return any(m in text for m in markers)
    
    def _check_json_artifacts(self, text: str) -> BrokenStringIssue | None:
        """Check for JSON array artifacts."""
        text_stripped = text.strip()
        
        # Starts with JSON array
        if text_stripped.startswith('["') or text_stripped.startswith("['"):
            return BrokenStringIssue(
                "json_artifact",
                "critical",
                "Starts with JSON array notation"
            )
        
        # Ends with JSON array
        if text_stripped.endswith('"]') or text_stripped.endswith("']"):
            return BrokenStringIssue(
                "json_artifact",
                "critical",
                "Ends with JSON array notation"
            )
        
        # Contains obvious JSON separators (multiple occurrences)
        if text.count('", "') >= 2 or text.count("', '") >= 2:
            return BrokenStringIssue(
                "json_artifact",
                "warning",
                "Contains JSON array separators"
            )
        
        return None
    
    def _check_encoding(self, text: str) -> BrokenStringIssue | None:
        """Check for encoding issues."""
        # Replacement character
        if '�' in text:
            return BrokenStringIssue(
                "encoding_error",
                "critical",
                "Contains replacement character (encoding error)"
            )
        
        # Null bytes or other control characters (except newlines/tabs)
        for char in text:
            if ord(char) < 32 and char not in '\n\r\t':
                return BrokenStringIssue(
                    "encoding_error",
                    "critical",
                    f"Contains control character (0x{ord(char):02x})"
                )
        
        return None
    
    def _check_truncation(self, original: str, translated: str) -> BrokenStringIssue | None:
        """Check if translation appears truncated."""
        # Remove tags for length comparison
        orig_clean = self._strip_tags(original)
        trans_clean = self._strip_tags(translated)
        
        if len(orig_clean) < 10:
            return None
        
        ratio = len(trans_clean) / len(orig_clean)
        
        if ratio < self.min_length_ratio:
            return BrokenStringIssue(
                "truncated",
                "warning",
                f"Translation too short ({ratio:.1%} of original)"
            )
        
        if ratio > self.max_length_ratio:
            return BrokenStringIssue(
                "too_long",
                "info",
                f"Translation unusually long ({ratio:.1%} of original)"
            )
        
        return None
    
    def _check_untranslated(self, original: str, translated: str) -> BrokenStringIssue | None:
        """Check if translation contains too much untranslated Latin text."""
        # Strip out tags and game codes
        trans_clean = self._strip_tags(translated)
        trans_clean = GAME_CODE_PATTERN.sub('', trans_clean)
        trans_clean = BRACKET_PLACEHOLDER.sub('', trans_clean)
        
        if len(trans_clean) < 10:
            return None
        
        latin_count = sum(1 for c in trans_clean if c in self.LATIN)
        cyrillic_count = sum(1 for c in trans_clean if c in self.CYRILLIC)
        
        total_letters = latin_count + cyrillic_count
        if total_letters < 5:
            return None
        
        latin_ratio = latin_count / total_letters
        
        # If more Latin than Cyrillic in a Russian translation, it's suspicious
        if latin_ratio > self.max_latin_ratio and cyrillic_count < latin_count:
            return BrokenStringIssue(
                "untranslated",
                "warning",
                f"Too much Latin text ({latin_ratio:.0%}), may be untranslated"
            )
        
        return None
    
    def _check_repetition(self, text: str) -> BrokenStringIssue | None:
        """Check for suspicious repetitions."""
        # Split into sentences/phrases
        sentences = re.split(r'[.!?。！？]\s*', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if len(sentences) < 2:
            return None
        
        # Check for exact duplicates
        seen = set()
        for s in sentences:
            if s in seen:
                return BrokenStringIssue(
                    "repetition",
                    "warning",
                    "Contains repeated sentences"
                )
            seen.add(s)
        
        return None
    
    def _check_incomplete(self, original: str, translated: str) -> BrokenStringIssue | None:
        """Check for incomplete translation (ends abruptly)."""
        trans_stripped = translated.rstrip()
        
        if not trans_stripped:
            return None
        
        # Check if original ends with punctuation but translation doesn't
        orig_ends_punct = bool(re.search(r'[.!?。！？"\'\)]$', original.rstrip()))
        trans_ends_punct = bool(re.search(r'[.!?。！？"\'\)]$', trans_stripped))
        
        if orig_ends_punct and not trans_ends_punct:
            # Check if it ends mid-word (no space before last char sequence)
            last_word = trans_stripped.split()[-1] if trans_stripped.split() else ""
            if len(last_word) > 2 and last_word[-1].isalpha():
                return BrokenStringIssue(
                    "incomplete",
                    "warning",
                    "Translation may be cut off (no ending punctuation)"
                )
        
        return None
    
    def _strip_tags(self, text: str) -> str:
        """Remove game tags and codes for clean comparison."""
        result = GAME_TAG_PATTERN.sub('', text)
        result = GAME_CODE_PATTERN.sub('', result)
        return result
    
    def is_broken(self, original: str, translated: str) -> bool:
        """Quick check if translation has any critical issues."""
        issues = self.detect_issues(original, translated)
        return any(i.severity == "critical" for i in issues)
    
    def get_critical_issues(self, original: str, translated: str) -> list[BrokenStringIssue]:
        """Get only critical issues."""
        issues = self.detect_issues(original, translated)
        return [i for i in issues if i.severity == "critical"]


@dataclass
class ValidationIssue:
    """Single validation issue."""
    
    id: str
    mismatches: str
    original: str
    translated: str
    
    @property
    def issue_type(self) -> str:
        """Classify the issue type."""
        if re.search(r"'\[\d+\]': 0 -> \d+", self.mismatches):
            return "numbered_brackets"  # LLM added [1], [2], etc.
        elif "'\\n'" in self.mismatches:
            return "newline_mismatch"
        elif re.search(r"'<[^>]+>': \d+ -> 0", self.mismatches):
            return "tag_translated"  # Game tag was translated
        elif re.search(r"'\[[^\]]+\]': \d+ -> 0", self.mismatches):
            return "placeholder_translated"  # [Something] was translated
        else:
            return "other"
    
    def can_autofix(self) -> bool:
        """Check if issue can be auto-fixed without LLM."""
        return self.issue_type == "numbered_brackets"
    
    def autofix(self) -> str:
        """Auto-fix simple issues like numbered brackets."""
        if self.issue_type == "numbered_brackets":
            # Remove [1], [2], etc. from start of translation
            return re.sub(r'^\[\d+\]\s*', '', self.translated)
        return self.translated


class IssueFixer:
    """Fix validation issues using LLM."""
    
    SYSTEM_PROMPT = """You are a translation quality fixer for a Chinese martial arts game "Where Winds Meet".

Your task: Fix ONLY the specific symbol/formatting issues in Russian translations, keeping the meaning intact.

## Issue Types and How to Fix:

### 1. Numbered brackets like [1], [2], [3]
These were incorrectly added by previous translation. REMOVE them.
Example:
- Original: "Latrine"
- Bad translation: "[1] Латрина"  
- Fixed: "Латрина"

### 2. Newline (\\n) mismatches
Restore the same number of \\n as in original, in logical places.
Example:
- Original: "Line one.\\nLine two."
- Bad: "Первая строка. Вторая строка."
- Fixed: "Первая строка.\\nВторая строка."

### 3. Game tags translated (SHOULD NOT BE)
Tags like <Something|123|#C|456> must be kept EXACTLY as in original, not translated.
Example:
- Original: "Increases <Max Attack|780|#C|151> by 10%"
- Bad: "Увеличивает <Макс. атака|780|#C|151> на 10%"
- Fixed: "Увеличивает <Max Attack|780|#C|151> на 10%"

### 4. Placeholder brackets translated (USUALLY OK)
Things like [Recruit Fellowship] → [Рекрутировать спутников] are often CORRECT.
Only fix if it breaks game functionality (contains codes/numbers).

## Response Format
Return a JSON array with one object per issue:
```json
[
  {
    "id": "issue_id",
    "action": "fix" | "keep",
    "fixed": "corrected translation or empty if keep",
    "reason": "brief explanation"
  }
]
```

Use "keep" if the translation is actually correct and doesn't need fixing.
Use "fix" and provide the corrected translation if there's a real problem.

IMPORTANT: 
- Keep ALL game codes like #Y, #E, {0}, {1:.1f} etc. unchanged
- Keep tag structure <name|num|#C|num> unchanged (but content might need to stay in English)
- Match \\n count exactly with original
- Do NOT add explanations inside the translation
"""

    def __init__(
        self,
        llm_client: LLMClient,
        batch_size: int = 5,
        log_callback: Callable[[str], None] | None = None,
    ):
        self._llm = llm_client
        self._batch_size = batch_size
        self._log = log_callback or (lambda x: None)
    
    def load_issues(self, issues_file: Path) -> list[ValidationIssue]:
        """Load issues from CSV."""
        issues = []
        with open(issues_file, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                issues.append(ValidationIssue(
                    id=row["ID"],
                    mismatches=row["Mismatches"],
                    original=row["Original"],
                    translated=row["Translated"],
                ))
        return issues
    
    def fix_issues(
        self,
        issues: list[ValidationIssue],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, str]:
        """
        Fix issues and return dict of {id: fixed_translation}.
        
        Returns only entries that were actually fixed.
        """
        fixes: dict[str, str] = {}
        
        # First, auto-fix simple issues
        autofix_count = 0
        remaining = []
        
        for issue in issues:
            if issue.can_autofix():
                fixed = issue.autofix()
                if fixed != issue.translated:
                    fixes[issue.id] = fixed
                    autofix_count += 1
            else:
                remaining.append(issue)
        
        if autofix_count > 0:
            self._log(f"Auto-fixed {autofix_count} simple issues (numbered brackets)")
        
        if not remaining:
            return fixes
        
        self._log(f"Processing {len(remaining)} issues with LLM...")
        
        # Process remaining with LLM in batches
        for i in range(0, len(remaining), self._batch_size):
            batch = remaining[i:i + self._batch_size]
            batch_num = i // self._batch_size + 1
            total_batches = (len(remaining) + self._batch_size - 1) // self._batch_size
            
            self._log(f"  Batch {batch_num}/{total_batches}...")
            
            try:
                batch_fixes = self._process_batch(batch)
                fixes.update(batch_fixes)
                
                if progress_callback:
                    progress_callback(i + len(batch), len(remaining))
                    
            except Exception as e:
                self._log(f"  Error in batch {batch_num}: {e}")
                logger.exception("Batch processing failed")
        
        return fixes
    
    def _process_batch(self, issues: list[ValidationIssue]) -> dict[str, str]:
        """Process a batch of issues with LLM."""
        # Build user message
        lines = ["Fix these translation issues:\n"]
        
        for i, issue in enumerate(issues, 1):
            lines.append(f"[{i}] ID: {issue.id}")
            lines.append(f"Issue: {issue.mismatches}")
            lines.append(f"Original (EN): {issue.original}")
            lines.append(f"Current (RU): {issue.translated}")
            lines.append("")
        
        user_message = "\n".join(lines)
        
        # Create texts list for LLM client
        texts = [{"id": issues[0].id, "english": user_message, "original": ""}]
        
        # Get LLM response
        response = self._llm.translate_batch_sync(texts, self.SYSTEM_PROMPT)
        
        # Parse response
        fixes = {}
        try:
            # Find JSON in response
            content = response[0]
            start = content.find("[")
            end = content.rfind("]") + 1
            
            if start != -1 and end > start:
                results = json.loads(content[start:end])
                
                for result in results:
                    if result.get("action") == "fix" and result.get("fixed"):
                        fixes[result["id"]] = result["fixed"]
                        self._log(f"    Fixed: {result['id']} - {result.get('reason', '')}")
                    elif result.get("action") == "keep":
                        self._log(f"    Kept: {result['id']} - {result.get('reason', '')}")
                        
        except json.JSONDecodeError as e:
            self._log(f"    Failed to parse LLM response: {e}")
            logger.error(f"JSON parse error: {e}\nResponse: {response[0][:500]}")
        
        return fixes
    
    def apply_fixes(
        self,
        fixes: dict[str, str],
        translated_csv: Path,
        output_csv: Path | None = None,
    ) -> int:
        """
        Apply fixes to translated CSV.
        
        Returns number of rows updated.
        """
        if output_csv is None:
            output_csv = translated_csv
        
        rows = []
        fieldnames = None
        
        with open(translated_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        updated = 0
        for row in rows:
            if row["ID"] in fixes:
                row["Russian"] = fixes[row["ID"]]
                updated += 1
        
        with open(output_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        
        return updated

