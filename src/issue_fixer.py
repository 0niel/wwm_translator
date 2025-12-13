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


GAME_TAG_PATTERN = re.compile(r'<[^>]+\|[^>]+>')
GAME_CODE_PATTERN = re.compile(r'#[YyEeCcRrGgBbWw]|{\d+[^}]*}')
BRACKET_PLACEHOLDER = re.compile(r'\[[^\]]+\]')


@dataclass
class BrokenStringIssue:
    """Detected broken string issue."""
    
    issue_type: str
    severity: str
    description: str
    
    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.issue_type}: {self.description}"


@dataclass
class BrokenStringDetector:
    """Detect various types of broken/corrupted translations."""
    
    min_length_ratio: float = 0.3
    max_length_ratio: float = 3.0
    max_latin_ratio: float = 0.4
    
    CYRILLIC = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ')
    LATIN = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    
    COMMON_ENGLISH_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
        'from', 'up', 'about', 'into', 'over', 'after', 'beneath', 'under',
        'above', 'no', 'not', 'or', 'and', 'but', 'if', 'then', 'else',
        'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now',
        'skill', 'skills', 'attack', 'damage', 'defense', 'health', 'combat',
        'increase', 'increases', 'decrease', 'decreases', 'effect', 'effects',
        'prison', 'riding', 'lightness', 'mystic', 'wallstride',
    }
    
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
        
        if self._has_error_markers(translated):
            issues.append(BrokenStringIssue(
                "error_marker",
                "critical",
                "Contains error marker like [MISSING] or [PARSE ERROR]"
            ))
        
        if json_issue := self._check_json_artifacts(translated):
            issues.append(json_issue)
        
        if encoding_issue := self._check_encoding(translated):
            issues.append(encoding_issue)
        
        if untrans_issue := self._check_completely_untranslated(original, translated):
            issues.append(untrans_issue)
        
        if broken_issue := self._check_broken_string(original, translated):
            issues.append(broken_issue)
        
        if len(original) > 20:
            if truncation_issue := self._check_truncation(original, translated):
                issues.append(truncation_issue)
        
        if len(original) > 10:
            if latin_issue := self._check_untranslated(original, translated):
                issues.append(latin_issue)
        
        if repetition_issue := self._check_repetition(translated):
            issues.append(repetition_issue)
        
        if incomplete_issue := self._check_incomplete(original, translated):
            issues.append(incomplete_issue)
        
        return issues
    
    def _has_error_markers(self, text: str) -> bool:
        """Check for error markers."""
        markers = ["[MISSING]", "[PARSE ERROR]", "[ERROR]", "[INCOMPLETE]"]
        return any(m in text for m in markers)
    
    def _check_completely_untranslated(self, original: str, translated: str) -> BrokenStringIssue | None:
        """Check if translation is completely untranslated (all English)."""
        trans_clean = self._strip_tags(translated)
        trans_clean = GAME_CODE_PATTERN.sub('', trans_clean)
        trans_clean = BRACKET_PLACEHOLDER.sub('', trans_clean)
        
        if len(trans_clean) < 5:
            return None
        
        orig_clean = self._strip_tags(original)
        orig_clean = GAME_CODE_PATTERN.sub('', orig_clean)
        orig_clean = BRACKET_PLACEHOLDER.sub('', orig_clean)
        
        if trans_clean.strip().lower() == orig_clean.strip().lower():
            return BrokenStringIssue(
                "not_translated",
                "critical",
                "Translation is identical to original (not translated)"
            )
        
        cyrillic_count = sum(1 for c in trans_clean if c in self.CYRILLIC)
        latin_count = sum(1 for c in trans_clean if c in self.LATIN)
        
        if cyrillic_count == 0 and latin_count >= 5:
            words = trans_clean.lower().split()
            english_words_found = sum(1 for w in words if w.strip('.,!?;:') in self.COMMON_ENGLISH_WORDS)
            
            if english_words_found >= 2 or latin_count >= 10:
                return BrokenStringIssue(
                    "not_translated",
                    "critical",
                    f"No Cyrillic text found, appears to be untranslated English ({latin_count} Latin chars)"
                )
        
        return None
    
    def _check_broken_string(self, original: str, translated: str) -> BrokenStringIssue | None:
        """Check for broken/gibberish strings like partial words or corrupted text."""
        trans_stripped = translated.strip()
        
        if len(trans_stripped) < 3:
            return None
        
        if ' ' not in trans_stripped and len(trans_stripped) >= 5:
            has_cyrillic = any(c in self.CYRILLIC for c in trans_stripped)
            has_latin = any(c in self.LATIN for c in trans_stripped)
            
            if has_cyrillic and has_latin:
                return BrokenStringIssue(
                    "broken_string",
                    "critical",
                    "Mixed Cyrillic and Latin in single word (possibly corrupted)"
                )
            
            if has_latin and not has_cyrillic:
                orig_clean = self._strip_tags(original).strip()
                if len(orig_clean) > len(trans_stripped) * 2:
                    return BrokenStringIssue(
                        "broken_string",
                        "critical",
                        f"Single Latin word '{trans_stripped}' for longer original text"
                    )
                
                if trans_stripped[-2:].lower() in ('li', 'le', 'ri', 're') and len(trans_stripped) >= 8:
                    if trans_stripped.lower() not in {'generally', 'immediately', 'naturally', 'carefully'}:
                        return BrokenStringIssue(
                            "broken_string",
                            "warning",
                            f"Suspicious word ending: '{trans_stripped}' (possibly truncated)"
                        )
        
        letters = sum(1 for c in trans_stripped if c in self.CYRILLIC or c in self.LATIN)
        if len(trans_stripped) >= 5 and letters / len(trans_stripped) < 0.3:
            return BrokenStringIssue(
                "broken_string",
                "warning",
                "Very few letters in translation (mostly symbols/numbers)"
            )
        
        return None
    
    def _check_json_artifacts(self, text: str) -> BrokenStringIssue | None:
        """Check for JSON array artifacts."""
        text_stripped = text.strip()
        
        if text_stripped.startswith('["') or text_stripped.startswith("['"):
            return BrokenStringIssue(
                "json_artifact",
                "critical",
                "Starts with JSON array notation"
            )
        
        if text_stripped.endswith('"]') or text_stripped.endswith("']"):
            return BrokenStringIssue(
                "json_artifact",
                "critical",
                "Ends with JSON array notation"
            )
        
        if text.count('", "') >= 2 or text.count("', '") >= 2:
            return BrokenStringIssue(
                "json_artifact",
                "warning",
                "Contains JSON array separators"
            )
        
        return None
    
    def _check_encoding(self, text: str) -> BrokenStringIssue | None:
        """Check for encoding issues."""
        if '�' in text:
            return BrokenStringIssue(
                "encoding_error",
                "critical",
                "Contains replacement character (encoding error)"
            )
        
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
        
        words = trans_clean.lower().split()
        english_words_found = sum(1 for w in words if w.strip('.,!?;:') in self.COMMON_ENGLISH_WORDS)
        
        if english_words_found >= 3:
            return BrokenStringIssue(
                "untranslated",
                "critical",
                f"Contains {english_words_found} common English words, likely untranslated"
            )
        
        if latin_ratio > self.max_latin_ratio and cyrillic_count < latin_count:
            severity = "critical" if latin_ratio > 0.7 else "warning"
            return BrokenStringIssue(
                "untranslated",
                severity,
                f"Too much Latin text ({latin_ratio:.0%}), may be untranslated"
            )
        
        return None
    
    def _check_repetition(self, text: str) -> BrokenStringIssue | None:
        """Check for suspicious repetitions."""
        sentences = re.split(r'[.!?。！？]\s*', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if len(sentences) < 2:
            return None
        
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
        
        orig_ends_punct = bool(re.search(r'[.!?。！？"\'\)]$', original.rstrip()))
        trans_ends_punct = bool(re.search(r'[.!?。！？"\'\)]$', trans_stripped))
        
        if orig_ends_punct and not trans_ends_punct:
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
            return "numbered_brackets"
        elif "'\\n'" in self.mismatches:
            return "newline_mismatch"
        elif re.search(r"'<[^>]+>': \d+ -> 0", self.mismatches):
            return "tag_translated"
        elif re.search(r"'\[[^\]]+\]': \d+ -> 0", self.mismatches):
            return "placeholder_translated"
        else:
            return "other"
    
    def is_untranslated(self) -> bool:
        """Check if the translation appears to be untranslated English."""
        detector = BrokenStringDetector()
        issues = detector.detect_issues(self.original, self.translated)
        return any(i.issue_type in ("not_translated", "untranslated") and i.severity == "critical" 
                   for i in issues)
    
    def is_broken(self) -> bool:
        """Check if the translation appears to be broken/corrupted."""
        detector = BrokenStringDetector()
        issues = detector.detect_issues(self.original, self.translated)
        return any(i.issue_type == "broken_string" and i.severity == "critical" 
                   for i in issues)
    
    def can_autofix(self) -> bool:
        """Check if issue can be auto-fixed without LLM."""
        return self.issue_type == "numbered_brackets"
    
    def autofix(self) -> str:
        """Auto-fix simple issues like numbered brackets."""
        if self.issue_type == "numbered_brackets":
            return re.sub(r'^\[\d+\]\s*', '', self.translated)
        return self.translated


class IssueFixer:
    """Fix validation issues using LLM."""
    
    SYSTEM_PROMPT = """You are a translation quality fixer for a Chinese martial arts game "Where Winds Meet".

Your task: Fix translation issues in Russian translations. This includes fixing formatting AND translating untranslated text.

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

### 5. UNTRANSLATED TEXT (CRITICAL!)
If "Current (RU)" is still in English instead of Russian - TRANSLATE IT FULLY.
Example:
- Original: "No Wallstride, lightness skill, riding, combat, or Mystic Skill in the prison!"
- Bad: "No Wallstride, lightness skill, riding, combat, or Mystic Skill in the prison!"
- Fixed: "В тюрьме запрещены бег по стенам, навыки лёгкости, верховая езда, бой и мистические умения!"

### 6. BROKEN/CORRUPTED STRINGS (CRITICAL!)
If "Current (RU)" looks like gibberish, a partial word, or corrupted text - RETRANSLATE.
Example:
- Original: "Sentence"
- Bad: "Sentenceli" (corrupted)
- Fixed: "Предложение"

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
- Keep tag structure <name|num|#C|num> unchanged (content inside tags stays in English)
- Match \\n count exactly with original
- Do NOT add explanations inside the translation
- ALWAYS translate English text to Russian (except game tags and codes)
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
    
    def scan_for_broken_strings(
        self,
        translated_csv: Path,
        original_col: str = "English",
        translated_col: str = "Russian",
    ) -> list[ValidationIssue]:
        """Scan translated CSV for broken/untranslated strings."""
        detector = BrokenStringDetector()
        issues = []
        
        with open(translated_csv, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            
            for row in reader:
                row_id = row.get("ID", "")
                original = row.get(original_col, "")
                translated = row.get(translated_col, "")
                
                if not original or not translated:
                    continue
                
                detected = detector.detect_issues(original, translated)
                critical = [i for i in detected if i.severity == "critical"]
                
                if critical:
                    mismatch_str = "; ".join(str(i) for i in critical)
                    issues.append(ValidationIssue(
                        id=row_id,
                        mismatches=mismatch_str,
                        original=original,
                        translated=translated,
                    ))
        
        return issues
    
    def fix_issues(
        self,
        issues: list[ValidationIssue],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, str]:
        """Fix issues and return dict of {id: fixed_translation}."""
        fixes: dict[str, str] = {}
        
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
        lines = ["Fix these translation issues:\n"]
        
        for i, issue in enumerate(issues, 1):
            lines.append(f"[{i}] ID: {issue.id}")
            lines.append(f"Issue: {issue.mismatches}")
            lines.append(f"Original (EN): {issue.original}")
            lines.append(f"Current (RU): {issue.translated}")
            lines.append("")
        
        user_message = "\n".join(lines)
        
        texts = [{"id": issues[0].id, "english": user_message, "original": ""}]
        
        response = self._llm.translate_batch_sync(texts, self.SYSTEM_PROMPT)
        
        fixes = {}
        try:
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
        """Apply fixes to translated CSV."""
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
