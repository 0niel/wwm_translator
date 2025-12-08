#!/usr/bin/env python3
"""
Gender Fixer for Russian Translations

Fixes grammatical gender in Russian translations by:
1. Detecting gender from English/Chinese context (he/she, 他/她)
2. Using name dictionaries to determine character gender
3. Morphological analysis with pymorphy3
4. Pattern-based verb ending corrections

NO LLM used - pure algorithmic approach.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

import pymorphy3
from pymorphy3.analyzer import Parse


class Gender(Enum):
    MALE = "masc"
    FEMALE = "femn"
    NEUTRAL = "neut"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_pymorphy(cls, tag) -> "Gender":
        if "masc" in tag:
            return cls.MALE
        if "femn" in tag:
            return cls.FEMALE
        if "neut" in tag:
            return cls.NEUTRAL
        return cls.UNKNOWN


@dataclass
class GenderContext:
    """Context for gender detection."""
    english: str = ""
    chinese: str = ""
    russian: str = ""
    detected_gender: Gender = Gender.UNKNOWN
    confidence: float = 0.0
    source: str = ""  # Where gender was detected from


@dataclass
class GenderFix:
    """A single gender fix."""
    entry_id: str
    original: str
    fixed: str
    changes: list[tuple[str, str]] = field(default_factory=list)  # (old, new)
    detected_gender: Gender = Gender.UNKNOWN
    confidence: float = 0.0


class GenderDetector:
    """
    Detects grammatical gender from multilingual context.
    
    Priority:
    1. Chinese pronouns (他/她) - most reliable
    2. Chinese titles/roles (公子/姑娘)
    3. English pronouns (he/she)
    4. English role words (man/woman)
    5. Speaker context (first person markers)
    """
    
    # English pronouns - strongest gender indicators
    EN_PRONOUNS_MALE = {"he", "him", "his", "himself"}
    EN_PRONOUNS_FEMALE = {"she", "her", "hers", "herself"}
    
    # English role words - medium confidence
    EN_ROLES_MALE = {
        "man", "boy", "father", "brother", "son", "husband",
        "king", "prince", "lord", "sir", "master", "mister", "mr",
        "uncle", "grandfather", "nephew", "gentleman", "guy",
        "warrior", "hero", "monk", "elder brother", "young master",
    }
    
    EN_ROLES_FEMALE = {
        "woman", "girl", "mother", "sister", "daughter", "wife",
        "queen", "princess", "lady", "madam", "miss", "mrs", "ms",
        "aunt", "grandmother", "niece", "maiden", "heroine",
        "young lady", "elder sister", "young miss",
    }
    
    # Chinese pronouns - strongest indicators (they explicitly mark gender)
    # 他 = he (male), 她 = she (female), 它 = it (neuter)
    ZH_PRONOUN_MALE = "他"
    ZH_PRONOUN_FEMALE = "她"
    
    # Chinese titles/roles - context for who is speaking/being addressed
    ZH_TITLES_MALE = {
        "公子",    # gōngzǐ - young master
        "少侠",    # shǎoxiá - young hero
        "大侠",    # dàxiá - great hero
        "侠士",    # xiáshì - warrior/hero
        "先生",    # xiānsheng - mister/sir
        "老爷",    # lǎoye - master/lord
        "爷",      # yé - grandfather/sir
        "兄",      # xiōng - elder brother
        "弟",      # dì - younger brother
        "兄弟",    # xiōngdì - brothers
        "郎君",    # lángjūn - husband/gentleman
        "壮士",    # zhuàngshì - brave warrior
        "少年",    # shàonián - young man
        "小子",    # xiǎozi - boy/lad
        "老头",    # lǎotóu - old man
        "和尚",    # héshang - monk
        "道士",    # dàoshi - taoist priest
    }
    
    ZH_TITLES_FEMALE = {
        "姑娘",    # gūniang - young lady/miss
        "小姐",    # xiǎojiě - miss
        "娘子",    # niángzi - lady/wife
        "夫人",    # fūrén - madam/wife
        "女侠",    # nǚxiá - heroine
        "姐",      # jiě - elder sister
        "妹",      # mèi - younger sister
        "姐妹",    # jiěmèi - sisters
        "姐姐",    # jiějie - elder sister
        "妹妹",    # mèimei - younger sister
        "婆婆",    # pópó - grandmother
        "娘",      # niáng - mother/lady
        "女子",    # nǚzǐ - woman
        "少女",    # shàonǚ - young woman
        "丫头",    # yātou - girl/servant girl
        "姨",      # yí - aunt
        "嫂",      # sǎo - sister-in-law
        "仙女",    # xiānnǚ - fairy/goddess
        "仙子",    # xiānzǐ - fairy
    }
    
    # First person markers in Chinese - when the speaker refers to themselves
    ZH_FIRST_PERSON = {"我", "吾", "在下", "本人", "老夫", "老身", "奴家", "小女子", "小生"}
    ZH_FIRST_PERSON_MALE = {"老夫", "小生", "在下"}  # Male self-reference
    ZH_FIRST_PERSON_FEMALE = {"老身", "奴家", "小女子"}  # Female self-reference
    
    def __init__(self):
        self._name_gender_cache: dict[str, Gender] = {}
    
    def detect_from_chinese(self, text: str) -> tuple[Gender, float, str]:
        """
        Detect gender from Chinese text with detailed analysis.
        Returns: (gender, confidence, reason)
        """
        if not text:
            return Gender.UNKNOWN, 0.0, ""
        
        # 1. Check first-person gender markers (highest priority for speaker's gender)
        for marker in self.ZH_FIRST_PERSON_FEMALE:
            if marker in text:
                return Gender.FEMALE, 0.95, f"zh_first_person:{marker}"
        
        for marker in self.ZH_FIRST_PERSON_MALE:
            if marker in text:
                return Gender.MALE, 0.95, f"zh_first_person:{marker}"
        
        # 2. Count third-person pronouns (他/她)
        # Be careful: we want to identify WHO the subject is
        male_pronoun_count = text.count(self.ZH_PRONOUN_MALE)
        female_pronoun_count = text.count(self.ZH_PRONOUN_FEMALE)
        
        # Strong signal if only one type of pronoun
        if female_pronoun_count > 0 and male_pronoun_count == 0:
            conf = min(0.90, 0.70 + female_pronoun_count * 0.05)
            return Gender.FEMALE, conf, f"zh_pronoun:她x{female_pronoun_count}"
        
        if male_pronoun_count > 0 and female_pronoun_count == 0:
            conf = min(0.90, 0.70 + male_pronoun_count * 0.05)
            return Gender.MALE, conf, f"zh_pronoun:他x{male_pronoun_count}"
        
        # 3. Check titles/roles
        female_titles = [t for t in self.ZH_TITLES_FEMALE if t in text]
        male_titles = [t for t in self.ZH_TITLES_MALE if t in text]
        
        if female_titles and not male_titles:
            return Gender.FEMALE, 0.80, f"zh_title:{female_titles[0]}"
        
        if male_titles and not female_titles:
            return Gender.MALE, 0.80, f"zh_title:{male_titles[0]}"
        
        # 4. If both pronouns present, use the majority
        if female_pronoun_count > male_pronoun_count * 2:
            return Gender.FEMALE, 0.60, "zh_pronoun_majority:她"
        
        if male_pronoun_count > female_pronoun_count * 2:
            return Gender.MALE, 0.60, "zh_pronoun_majority:他"
        
        return Gender.UNKNOWN, 0.0, ""
    
    def detect_from_english(self, text: str) -> tuple[Gender, float, str]:
        """
        Detect gender from English text.
        Returns: (gender, confidence, reason)
        """
        if not text:
            return Gender.UNKNOWN, 0.0, ""
        
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        # Check pronouns first (strongest signal)
        male_pronouns = words & self.EN_PRONOUNS_MALE
        female_pronouns = words & self.EN_PRONOUNS_FEMALE
        
        if female_pronouns and not male_pronouns:
            return Gender.FEMALE, 0.85, f"en_pronoun:{list(female_pronouns)[0]}"
        
        if male_pronouns and not female_pronouns:
            return Gender.MALE, 0.85, f"en_pronoun:{list(male_pronouns)[0]}"
        
        # Check role words
        male_roles = words & self.EN_ROLES_MALE
        female_roles = words & self.EN_ROLES_FEMALE
        
        # Also check multi-word roles
        for role in ["young lady", "elder sister", "young master", "elder brother"]:
            if role in text_lower:
                if role in ["young lady", "elder sister"]:
                    female_roles.add(role)
                else:
                    male_roles.add(role)
        
        if female_roles and not male_roles:
            return Gender.FEMALE, 0.70, f"en_role:{list(female_roles)[0]}"
        
        if male_roles and not female_roles:
            return Gender.MALE, 0.70, f"en_role:{list(male_roles)[0]}"
        
        return Gender.UNKNOWN, 0.0, ""
    
    def detect_speaker_from_russian(self, text: str) -> tuple[Gender, float, str]:
        """
        Detect gender from Russian text patterns that indicate speaker identity.
        This is used as a fallback/confirmation.
        """
        if not text:
            return Gender.UNKNOWN, 0.0, ""
        
        # Look for female self-references in Russian translation
        female_markers = [
            "сама", "одна", "готова", "рада", "должна", "уверена",
            "согласна", "довольна", "счастлива",
        ]
        
        male_markers = [
            "сам", "один", "готов", "рад", "должен", "уверен",
            "согласен", "доволен", "счастлив",
        ]
        
        text_lower = text.lower()
        
        # Check "я + marker" patterns
        for marker in female_markers:
            if re.search(rf'\bя\s+(?:\w+\s+){{0,2}}{marker}\b', text_lower):
                return Gender.FEMALE, 0.50, f"ru_marker:{marker}"
        
        for marker in male_markers:
            if re.search(rf'\bя\s+(?:\w+\s+){{0,2}}{marker}\b', text_lower):
                return Gender.MALE, 0.50, f"ru_marker:{marker}"
        
        return Gender.UNKNOWN, 0.0, ""
    
    def detect(self, context: GenderContext) -> GenderContext:
        """
        Detect gender from all available context.
        
        Priority:
        1. Chinese first-person markers (老身/奴家 vs 老夫/小生)
        2. Chinese pronouns (他/她)
        3. Chinese titles
        4. English pronouns
        5. English roles
        """
        best_gender = Gender.UNKNOWN
        best_confidence = 0.0
        best_source = ""
        
        # Try Chinese first (most reliable for this game)
        gender, conf, reason = self.detect_from_chinese(context.chinese)
        if conf > best_confidence:
            best_gender = gender
            best_confidence = conf
            best_source = reason
        
        # Try English if Chinese didn't give high confidence
        if best_confidence < 0.8:
            gender, conf, reason = self.detect_from_english(context.english)
            if conf > best_confidence:
                best_gender = gender
                best_confidence = conf
                best_source = reason
        
        # Use Russian as confirmation or weak fallback
        if best_confidence < 0.6:
            gender, conf, reason = self.detect_speaker_from_russian(context.russian)
            # Only use if nothing else found or as confirmation
            if best_gender == Gender.UNKNOWN:
                best_gender = gender
                best_confidence = conf
                best_source = reason
            elif gender == best_gender:
                # Confirmation - boost confidence slightly
                best_confidence = min(0.95, best_confidence + 0.1)
        
        context.detected_gender = best_gender
        context.confidence = best_confidence
        context.source = best_source
        
        return context


class RussianMorphology:
    """Russian morphological analyzer and transformer."""
    
    def __init__(self):
        self.morph = pymorphy3.MorphAnalyzer()
        
        # Past tense verb ending patterns
        self._past_male_pattern = re.compile(
            r'\b(\w+)(л|лся|лось)\b',
            re.IGNORECASE | re.UNICODE
        )
        self._past_female_pattern = re.compile(
            r'\b(\w+)(ла|лась)\b',
            re.IGNORECASE | re.UNICODE
        )
    
    def get_word_gender(self, word: str) -> Gender:
        """Get grammatical gender of a word."""
        parsed = self.morph.parse(word)
        if not parsed:
            return Gender.UNKNOWN
        
        # Get most probable parse
        best = parsed[0]
        return Gender.from_pymorphy(best.tag)
    
    def is_short_form(self, word: str) -> bool:
        """
        Check if word is a short adjective (ADJS) or short participle (PRTS).
        Examples: готов, рада, уверен, взволнован, удивлена
        """
        parsed = self.morph.parse(word)
        if not parsed:
            return False
        
        best = parsed[0]
        # ADJS = short adjective, PRTS = short participle
        return 'ADJS' in best.tag or 'PRTS' in best.tag
    
    def get_short_form_gender(self, word: str) -> Gender:
        """Get gender of a short adjective/participle."""
        parsed = self.morph.parse(word)
        if not parsed:
            return Gender.UNKNOWN
        
        best = parsed[0]
        if 'ADJS' not in best.tag and 'PRTS' not in best.tag:
            return Gender.UNKNOWN
        
        return Gender.from_pymorphy(best.tag)
    
    def change_short_form_gender(self, word: str, target_gender: Gender) -> str | None:
        """
        Change short adjective/participle to target gender.
        Uses pymorphy3 inflection with smart parsing selection.
        
        Problem: pymorphy can give wrong forms (уверенна instead of уверена)
        Solution: Try all parsings and prefer PRTS (participle) over ADJS (adjective)
        """
        parsed = self.morph.parse(word)
        if not parsed:
            return None
        
        # Find all valid short form parsings
        short_form_parses = [
            p for p in parsed
            if 'ADJS' in p.tag or 'PRTS' in p.tag
        ]
        
        if not short_form_parses:
            return None
        
        # Prefer PRTS (participle) over ADJS (adjective) - usually more accurate
        prts_parses = [p for p in short_form_parses if 'PRTS' in p.tag]
        best = prts_parses[0] if prts_parses else short_form_parses[0]
        
        current_gender = Gender.from_pymorphy(best.tag)
        if current_gender == target_gender or current_gender == Gender.UNKNOWN:
            return None
        
        try:
            if target_gender == Gender.MALE:
                new_form = best.inflect({'masc', 'sing'})
            elif target_gender == Gender.FEMALE:
                new_form = best.inflect({'femn', 'sing'})
            else:
                return None
            
            if new_form and new_form.word != word.lower():
                # Preserve original case
                result = new_form.word
                if word[0].isupper():
                    result = result.capitalize()
                return result
        except Exception:
            pass
        
        return None
    
    def find_short_forms_after_pronoun(
        self, 
        text: str, 
        pronoun: str = "я"
    ) -> list[tuple[str, Gender, int, int]]:
        """
        Find short adjectives/participles after a pronoun.
        Pattern: "я готов", "я была удивлена", "ты уверен", "я не уверен"
        
        Returns: [(word, gender, start, end), ...]
        """
        results = []
        
        # Find all occurrences of the pronoun
        pronoun_pattern = rf'\b{pronoun}\b'
        
        for pronoun_match in re.finditer(pronoun_pattern, text, re.IGNORECASE | re.UNICODE):
            pronoun_end = pronoun_match.end()
            
            # Look at the next several words after the pronoun (up to 5 words, ~50 chars)
            search_region = text[pronoun_end:pronoun_end + 60]
            
            # Find all words in this region
            words_in_region = list(re.finditer(r'\b(\w+)\b', search_region, re.UNICODE))
            
            # Check first 5 words for short forms
            for word_match in words_in_region[:5]:
                word = word_match.group(1)
                
                # Skip very short words and common particles
                if len(word) < 3 or word.lower() in {
                    'не', 'бы', 'же', 'ли', 'да', 'ну', 'уж', 'вот', 
                    'был', 'была', 'было', 'были',  # Skip auxiliary verbs (handled separately)
                    'буду', 'будет', 'будешь',
                    'это', 'это', 'всё', 'так', 'тут', 'там',
                }:
                    continue
                
                # Check if it's a short form (ADJS or PRTS)
                parsed = self.morph.parse(word)
                if not parsed:
                    continue
                
                # Find best short form parse
                best_short = None
                for parse in parsed:
                    if 'ADJS' in parse.tag or 'PRTS' in parse.tag:
                        gender = Gender.from_pymorphy(parse.tag)
                        if gender in (Gender.MALE, Gender.FEMALE):
                            best_short = (parse, gender)
                            break
                
                if not best_short:
                    continue
                
                parse, gender = best_short
                
                # Filter out false positives:
                # If the PRIMARY interpretation is NOUN and short form is secondary,
                # AND the word doesn't follow typical short adj patterns, skip it
                primary = parsed[0]
                if 'NOUN' in primary.tag and primary.score > parse.score * 1.5:
                    # Strong noun interpretation - likely a noun, not short adj
                    # Exception: if it's right after "я/ты" with no words between
                    continue
                
                # Calculate absolute position
                abs_start = pronoun_end + word_match.start(1)
                abs_end = pronoun_end + word_match.end(1)
                results.append((word, gender, abs_start, abs_end))
        
        return results
    
    def find_gendered_verbs(self, text: str) -> list[tuple[str, Gender, int, int]]:
        """
        Find past tense verbs with their gender.
        Returns: [(word, gender, start, end), ...]
        """
        results = []
        
        # Find male form verbs
        for match in self._past_male_pattern.finditer(text):
            word = match.group(0)
            # Verify it's actually a verb
            parsed = self.morph.parse(word)
            if parsed and 'VERB' in parsed[0].tag and 'past' in parsed[0].tag:
                results.append((word, Gender.MALE, match.start(), match.end()))
        
        # Find female form verbs
        for match in self._past_female_pattern.finditer(text):
            word = match.group(0)
            parsed = self.morph.parse(word)
            if parsed and 'VERB' in parsed[0].tag and 'past' in parsed[0].tag:
                results.append((word, Gender.FEMALE, match.start(), match.end()))
        
        return sorted(results, key=lambda x: x[2])
    
    def change_verb_gender(self, verb: str, target_gender: Gender) -> str | None:
        """
        Change verb to target gender.
        Returns new form or None if unchanged/impossible.
        """
        parsed = self.morph.parse(verb)
        if not parsed:
            return None
        
        best = parsed[0]
        
        # Must be a past tense verb
        if 'VERB' not in best.tag or 'past' not in best.tag:
            return None
        
        current_gender = Gender.from_pymorphy(best.tag)
        if current_gender == target_gender:
            return None
        
        # Try to inflect to target gender
        try:
            if target_gender == Gender.MALE:
                new_form = best.inflect({'masc', 'sing', 'past'})
            elif target_gender == Gender.FEMALE:
                new_form = best.inflect({'femn', 'sing', 'past'})
            else:
                return None
            
            if new_form and new_form.word != verb.lower():
                # Preserve original case
                if verb[0].isupper():
                    return new_form.word.capitalize()
                return new_form.word
        except Exception:
            pass
        
        return None
    
    def find_gendered_adjectives(self, text: str) -> list[tuple[str, Gender, int, int]]:
        """Find adjectives/participles with grammatical gender."""
        results = []
        words = re.finditer(r'\b(\w+)\b', text, re.UNICODE)
        
        for match in words:
            word = match.group(0)
            if len(word) < 3:
                continue
            
            parsed = self.morph.parse(word)
            if not parsed:
                continue
            
            best = parsed[0]
            # Check if it's an adjective or participle with gender
            if ('ADJF' in best.tag or 'PRTF' in best.tag) and 'sing' in best.tag:
                gender = Gender.from_pymorphy(best.tag)
                if gender in (Gender.MALE, Gender.FEMALE):
                    results.append((word, gender, match.start(), match.end()))
        
        return results
    
    def change_adjective_gender(self, adj: str, target_gender: Gender) -> str | None:
        """Change adjective/participle to target gender."""
        parsed = self.morph.parse(adj)
        if not parsed:
            return None
        
        best = parsed[0]
        
        if 'ADJF' not in best.tag and 'PRTF' not in best.tag:
            return None
        
        try:
            if target_gender == Gender.MALE:
                new_form = best.inflect({'masc', 'sing', 'nomn'})
            elif target_gender == Gender.FEMALE:
                new_form = best.inflect({'femn', 'sing', 'nomn'})
            else:
                return None
            
            if new_form and new_form.word != adj.lower():
                if adj[0].isupper():
                    return new_form.word.capitalize()
                return new_form.word
        except Exception:
            pass
        
        return None


class GenderFixer:
    """Main class to fix gender in translations."""
    
    def __init__(
        self,
        min_confidence: float = 0.5,
        log_callback: Callable[[str], None] | None = None,
    ):
        self.detector = GenderDetector()
        self.morphology = RussianMorphology()
        self.min_confidence = min_confidence
        self._log = log_callback or (lambda x: None)
        
        # Statistics
        self.stats = {
            "processed": 0,
            "fixed": 0,
            "verbs_changed": 0,
            "adjectives_changed": 0,
            "skipped_low_confidence": 0,
            "skipped_no_gender": 0,
        }
    
    def fix_entry(
        self,
        entry_id: str,
        russian: str,
        english: str = "",
        chinese: str = "",
    ) -> GenderFix | None:
        """
        Fix gender in a single translation entry.
        Returns GenderFix if changes made, None otherwise.
        
        CONSERVATIVE approach:
        - Only fix verbs that follow "я" or "ты" pronouns
        - Do NOT touch adjectives (too risky without syntax parsing)
        """
        self.stats["processed"] += 1
        
        if not russian:
            return None
        
        # Detect gender from context
        context = GenderContext(
            english=english,
            chinese=chinese,
            russian=russian,
        )
        context = self.detector.detect(context)
        
        if context.detected_gender == Gender.UNKNOWN:
            self.stats["skipped_no_gender"] += 1
            return None
        
        if context.confidence < self.min_confidence:
            self.stats["skipped_low_confidence"] += 1
            return None
        
        target_gender = context.detected_gender
        fixed_text = russian
        changes: list[tuple[str, str]] = []
        
        # CONSERVATIVE: Only fix verbs that clearly relate to speaker/addressee
        # Pattern: "я <verb>" or "ты <verb>" (with optional words between)
        
        # Find verbs after "я" (first person)
        first_person_patterns = [
            r'\bя\s+(\w+л)\b',           # я сделал
            r'\bя\s+(\w+ла)\b',          # я сделала
            r'\bя\s+(\w+лся)\b',         # я собрался
            r'\bя\s+(\w+лась)\b',        # я собралась
            r'\bя\s+\w+\s+(\w+л)\b',     # я уже сделал
            r'\bя\s+\w+\s+(\w+ла)\b',    # я уже сделала
            r'\bя\s+\w+\s+(\w+лся)\b',   # я уже собрался
            r'\bя\s+\w+\s+(\w+лась)\b',  # я уже собралась
        ]
        
        # Find verbs after "ты" (second person)  
        second_person_patterns = [
            r'\bты\s+(\w+л)\b',
            r'\bты\s+(\w+ла)\b',
            r'\bты\s+(\w+лся)\b',
            r'\bты\s+(\w+лась)\b',
            r'\bты\s+\w+\s+(\w+л)\b',
            r'\bты\s+\w+\s+(\w+ла)\b',
            r'\bты\s+\w+\s+(\w+лся)\b',
            r'\bты\s+\w+\s+(\w+лась)\b',
        ]
        
        all_patterns = first_person_patterns + second_person_patterns
        
        for pattern in all_patterns:
            for match in re.finditer(pattern, fixed_text, re.IGNORECASE | re.UNICODE):
                verb = match.group(1)
                verb_start = match.start(1)
                verb_end = match.end(1)
                
                # Verify it's actually a verb and get its gender
                parsed = self.morphology.morph.parse(verb)
                if not parsed:
                    continue
                
                best = parsed[0]
                if 'VERB' not in best.tag or 'past' not in best.tag:
                    continue
                
                current_gender = Gender.from_pymorphy(best.tag)
                
                if current_gender != target_gender and current_gender != Gender.UNKNOWN:
                    new_word = self.morphology.change_verb_gender(verb, target_gender)
                    if new_word and new_word != verb:
                        # Apply fix
                        fixed_text = fixed_text[:verb_start] + new_word + fixed_text[verb_end:]
                        changes.append((verb, new_word))
                        self.stats["verbs_changed"] += 1
                        break  # Re-search after modification
        
        # Fix short adjectives/participles after "я" using morphological analysis
        # ADJS = short adjective (краткое прилагательное): готов, рад, уверен
        # PRTS = short participle (краткое причастие): взволнован, удивлён
        short_form_fixes = self._fix_short_forms_after_pronoun(
            fixed_text, "я", target_gender
        )
        for old_word, new_word, start, end in short_form_fixes:
            fixed_text = fixed_text[:start] + new_word + fixed_text[end:]
            changes.append((old_word, new_word))
            self.stats["adjectives_changed"] += 1
        
        # Also fix after "ты" for second person
        short_form_fixes_ty = self._fix_short_forms_after_pronoun(
            fixed_text, "ты", target_gender
        )
        for old_word, new_word, start, end in short_form_fixes_ty:
            fixed_text = fixed_text[:start] + new_word + fixed_text[end:]
            changes.append((old_word, new_word))
            self.stats["adjectives_changed"] += 1
        
        if changes:
            self.stats["fixed"] += 1
            return GenderFix(
                entry_id=entry_id,
                original=russian,
                fixed=fixed_text,
                changes=changes,
                detected_gender=target_gender,
                confidence=context.confidence,
            )
        
        return None
    
    def _fix_short_forms_after_pronoun(
        self,
        text: str,
        pronoun: str,
        target_gender: Gender,
    ) -> list[tuple[str, str, int, int]]:
        """
        Find and fix short adjectives/participles after a pronoun.
        Uses pymorphy3 for automatic detection - no hardcoded word lists.
        
        Returns: [(old_word, new_word, start, end), ...]
        """
        fixes = []
        
        # Find all short forms after the pronoun
        short_forms = self.morphology.find_short_forms_after_pronoun(text, pronoun)
        
        for word, current_gender, start, end in reversed(short_forms):
            if current_gender != target_gender and current_gender != Gender.UNKNOWN:
                new_word = self.morphology.change_short_form_gender(word, target_gender)
                if new_word and new_word != word:
                    fixes.append((word, new_word, start, end))
        
        return fixes
    
    def process_csv(
        self,
        input_csv: Path,
        output_csv: Path | None = None,
        dry_run: bool = False,
    ) -> list[GenderFix]:
        """
        Process entire CSV file.
        Returns list of all fixes made.
        """
        if output_csv is None:
            output_csv = input_csv
        
        fixes: list[GenderFix] = []
        rows = []
        
        # Read
        with open(input_csv, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            fieldnames = reader.fieldnames
            
            for row in reader:
                fix = self.fix_entry(
                    entry_id=row.get("ID", ""),
                    russian=row.get("Russian", ""),
                    english=row.get("English", ""),
                    chinese=row.get("Original", ""),
                )
                
                if fix:
                    fixes.append(fix)
                    if not dry_run:
                        row["Russian"] = fix.fixed
                
                rows.append(row)
        
        # Write if not dry run
        if not dry_run and fixes:
            with open(output_csv, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                writer.writerows(rows)
        
        return fixes
    
    def get_stats(self) -> dict:
        """Get processing statistics."""
        return self.stats.copy()


# Quick patterns for common fixes without full morphological analysis
QUICK_GENDER_PATTERNS = [
    # (pattern, male_replacement, female_replacement)
    (r'\bсделал\b', 'сделал', 'сделала'),
    (r'\bсказал\b', 'сказал', 'сказала'),
    (r'\bпришёл\b', 'пришёл', 'пришла'),
    (r'\bушёл\b', 'ушёл', 'ушла'),
    (r'\bбыл\b', 'был', 'была'),
    (r'\bстал\b', 'стал', 'стала'),
    (r'\bвзял\b', 'взял', 'взяла'),
    (r'\bпонял\b', 'понял', 'поняла'),
    (r'\bувидел\b', 'увидел', 'увидела'),
    (r'\bуслышал\b', 'услышал', 'услышала'),
    (r'\bпошёл\b', 'пошёл', 'пошла'),
    (r'\bнашёл\b', 'нашёл', 'нашла'),
    (r'\bполучил\b', 'получил', 'получила'),
    (r'\bрешил\b', 'решил', 'решила'),
    (r'\bхотел\b', 'хотел', 'хотела'),
    (r'\bмог\b', 'мог', 'могла'),
    (r'\bзнал\b', 'знал', 'знала'),
    (r'\bдумал\b', 'думал', 'думала'),
    (r'\bвидел\b', 'видел', 'видела'),
    (r'\bслышал\b', 'слышал', 'слышала'),
    (r'\bждал\b', 'ждал', 'ждала'),
    (r'\bлюбил\b', 'любил', 'любила'),
    (r'\bжил\b', 'жил', 'жила'),
    (r'\bработал\b', 'работал', 'работала'),
    (r'\bиграл\b', 'играл', 'играла'),
    (r'\bчитал\b', 'читал', 'читала'),
    (r'\bписал\b', 'писал', 'писала'),
    (r'\bготов\b', 'готов', 'готова'),
    (r'\bрад\b', 'рад', 'рада'),
    (r'\bдолжен\b', 'должен', 'должна'),
    (r'\bуверен\b', 'уверен', 'уверена'),
    (r'\bсогласен\b', 'согласен', 'согласна'),
]


def quick_fix_gender(text: str, target_gender: Gender) -> tuple[str, list[tuple[str, str]]]:
    """
    Quick pattern-based gender fix without full morphological analysis.
    Faster but less accurate than full analysis.
    """
    changes = []
    result = text
    
    for pattern, male, female in QUICK_GENDER_PATTERNS:
        if target_gender == Gender.FEMALE:
            old = male
            new = female
        else:
            old = female
            new = male
        
        if re.search(pattern, result, re.IGNORECASE):
            # Check if already correct
            correct_pattern = new.replace('ё', '[её]')
            if re.search(rf'\b{correct_pattern}\b', result, re.IGNORECASE):
                continue
            
            # Replace
            def replace_preserve_case(match):
                matched = match.group(0)
                if matched[0].isupper():
                    return new.capitalize()
                return new
            
            wrong_pattern = old.replace('ё', '[её]')
            new_result = re.sub(
                rf'\b{wrong_pattern}\b',
                replace_preserve_case,
                result,
                flags=re.IGNORECASE
            )
            
            if new_result != result:
                changes.append((old, new))
                result = new_result
    
    return result, changes


if __name__ == "__main__":
    # Quick test
    fixer = GenderFixer(min_confidence=0.4)
    
    # Test cases
    test_cases = [
        {
            "id": "test1",
            "russian": "Я сделал это для тебя.",
            "english": "She did this for you.",
            "chinese": "她为你做了这个。",
        },
        {
            "id": "test2", 
            "russian": "Ты пришёл слишком поздно.",
            "english": "She came too late.",
            "chinese": "她来得太晚了。",
        },
        {
            "id": "test3",
            "russian": "Он был очень рад.",
            "english": "He was very happy.",
            "chinese": "他很高兴。",
        },
    ]
    
    print("Testing Gender Fixer:")
    print("=" * 50)
    
    for case in test_cases:
        fix = fixer.fix_entry(
            case["id"],
            case["russian"],
            case["english"],
            case["chinese"],
        )
        
        print(f"\nID: {case['id']}")
        print(f"EN: {case['english']}")
        print(f"ZH: {case['chinese']}")
        print(f"RU (original): {case['russian']}")
        
        if fix:
            print(f"RU (fixed): {fix.fixed}")
            print(f"Changes: {fix.changes}")
            print(f"Gender: {fix.detected_gender.name}, Confidence: {fix.confidence:.2f}")
        else:
            print("No changes needed")
    
    print("\n" + "=" * 50)
    print("Stats:", fixer.get_stats())

