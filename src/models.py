from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import TYPE_CHECKING, Self


if TYPE_CHECKING:
    from .config import FilteringConfig


class ErrorMarkers:
    """Markers for translation errors that need retry."""
    
    PARSE_ERROR = "[PARSE ERROR]"
    MISSING = "[MISSING]"
    
    # All markers that indicate a failed translation
    ALL = (PARSE_ERROR, MISSING)
    
    @classmethod
    def contains_error(cls, text: str) -> bool:
        """Check if text contains any error marker."""
        return any(marker in text for marker in cls.ALL)
    
    @classmethod
    def is_error_marker(cls, text: str) -> bool:
        """Check if text is exactly an error marker."""
        return text.strip() in cls.ALL


class TranslationStatus(Enum):
    """Translation entry status."""

    PENDING = auto()
    TRANSLATED = auto()
    SKIPPED = auto()
    ERROR = auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass(slots=True)
class TextEntry:
    """Single text entry from localization file."""

    number: int
    file_name: str
    all_blocks: int
    work_blocks: int
    current_block: int
    unknown: str
    text_id: str
    original_text: str

    def to_csv_row(self) -> list[str]:
        """Convert to CSV row."""
        return [
            str(self.number),
            self.file_name,
            str(self.all_blocks),
            str(self.work_blocks),
            str(self.current_block),
            self.unknown,
            self.text_id,
            self.original_text,
        ]

    @classmethod
    def from_csv_row(cls, row: list[str]) -> Self:
        """Create from CSV row."""
        return cls(
            number=int(row[0]),
            file_name=row[1],
            all_blocks=int(row[2]),
            work_blocks=int(row[3]),
            current_block=int(row[4]),
            unknown=row[5],
            text_id=row[6],
            original_text=row[7] if len(row) > 7 else "",
        )

    @classmethod
    def csv_header(cls) -> list[str]:
        """Get CSV header."""
        return [
            "Number",
            "File",
            "All Blocks",
            "Work Blocks",
            "Current Block",
            "Unknown",
            "ID",
            "OriginalText",
        ]


@dataclass(slots=True)
class TranslationEntry:
    """Entry for translation processing."""

    id: str
    english: str
    original: str
    translated: str = ""
    status: TranslationStatus = TranslationStatus.PENDING
    error_message: str = ""

    def should_translate(self, filtering: FilteringConfig) -> bool:
        """Check if entry should be translated."""
        text = self.english

        if not text or not text.strip():
            return False

        if len(text.strip()) < filtering.min_length:
            return False

        for pattern in filtering.skip_patterns:
            try:
                if re.match(pattern, text.strip()):
                    return False
            except re.error:
                continue

        return True

    def mark_translated(self, translation: str) -> None:
        """Mark as translated."""
        self.translated = translation
        self.status = TranslationStatus.TRANSLATED

    def mark_skipped(self) -> None:
        """Mark as skipped."""
        self.status = TranslationStatus.SKIPPED

    def mark_error(self, message: str) -> None:
        """Mark as error."""
        self.status = TranslationStatus.ERROR
        self.error_message = message

    def needs_retry(self) -> bool:
        """Check if translation contains error markers and needs retry."""
        return (
            self.status == TranslationStatus.TRANSLATED
            and self.translated
            and ErrorMarkers.contains_error(self.translated)
        )

    def mark_for_retry(self) -> None:
        """Reset entry for re-translation."""
        self.translated = ""
        self.status = TranslationStatus.PENDING
        self.error_message = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dict for LLM."""
        return {
            "id": self.id,
            "english": self.english,
            "original": self.original,
        }


@dataclass
class TranslationProgress:
    """Translation progress tracking."""

    total_entries: int = 0
    translated_entries: int = 0
    skipped_entries: int = 0
    error_entries: int = 0
    current_batch: int = 0
    total_batches: int = 0
    last_translated_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = ""
    source_file_hash: str = ""

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_entries == 0:
            return 0.0
        completed = self.translated_entries + self.skipped_entries
        return completed / self.total_entries * 100

    @property
    def remaining(self) -> int:
        """Get remaining entries."""
        return (
            self.total_entries - self.translated_entries - self.skipped_entries - self.error_entries
        )

    def update_timestamp(self) -> None:
        """Update timestamp."""
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        """Create from dict."""
        return cls(**data)


@dataclass(slots=True, frozen=True)
class ExtractionResult:
    """Result of extraction operation."""

    success: bool
    message: str
    files_extracted: int = 0
    texts_extracted: int = 0
    errors: tuple[str, ...] = ()

    @classmethod
    def ok(cls, message: str, files: int = 0, texts: int = 0) -> Self:
        """Create success result."""
        return cls(success=True, message=message, files_extracted=files, texts_extracted=texts)

    @classmethod
    def fail(cls, message: str, errors: list[str] | None = None) -> Self:
        """Create failure result."""
        return cls(success=False, message=message, errors=tuple(errors or []))


