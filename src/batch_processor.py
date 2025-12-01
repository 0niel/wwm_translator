from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import logging
import signal
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .config import AppConfig, EnvConfig, get_config, get_env_config
from .models import ErrorMarkers, TranslationEntry, TranslationProgress, TranslationStatus
from .tokenizer import CostConfig, TokenCounter


if TYPE_CHECKING:
    from .llm_client import LLMClient, PromptBuilder

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[TranslationProgress], None]
LogCallback = Callable[[str], None]


@dataclass
class ETACalculator:
    """Calculate estimated time remaining."""

    start_time: float = field(default_factory=time.time)
    items_done: int = 0
    total_items: int = 0
    _recent_times: list[float] = field(default_factory=list)

    def update(self, items_done: int) -> None:
        """Update progress."""
        now = time.time()
        if self.items_done > 0:
            self._recent_times.append(now)
            # Keep only last 20 measurements for moving average
            if len(self._recent_times) > 20:
                self._recent_times.pop(0)
        self.items_done = items_done

    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def items_per_second(self) -> float:
        """Average items per second."""
        if self.elapsed < 1 or self.items_done == 0:
            return 0.0
        return self.items_done / self.elapsed

    @property
    def eta_seconds(self) -> float:
        """Estimated seconds remaining."""
        if self.items_per_second == 0:
            return 0.0
        remaining = self.total_items - self.items_done
        return remaining / self.items_per_second

    def format_eta(self) -> str:
        """Format ETA as human-readable string."""
        eta = self.eta_seconds
        if eta <= 0:
            return "calculating..."

        if eta < 60:
            return f"{int(eta)}s"
        elif eta < 3600:
            mins, secs = divmod(int(eta), 60)
            return f"{mins}m {secs}s"
        else:
            hours, remainder = divmod(int(eta), 3600)
            mins = remainder // 60
            return f"{hours}h {mins}m"

    def format_elapsed(self) -> str:
        """Format elapsed time."""
        elapsed = int(self.elapsed)
        if elapsed < 60:
            return f"{elapsed}s"
        elif elapsed < 3600:
            mins, secs = divmod(elapsed, 60)
            return f"{mins}m {secs}s"
        else:
            hours, remainder = divmod(elapsed, 3600)
            mins = remainder // 60
            return f"{hours}h {mins}m"


@dataclass
class ProgressTracker:
    """Thread-safe progress persistence with atomic saves."""

    progress_dir: Path
    source_file: Path
    _progress: TranslationProgress | None = field(default=None, repr=False)
    _translations: dict[str, str] = field(default_factory=dict, repr=False)
    _dirty: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self.progress_dir = Path(self.progress_dir)
        self.source_file = Path(self.source_file)
        self.progress_dir.mkdir(parents=True, exist_ok=True)

    @property
    def progress_file(self) -> Path:
        return self.progress_dir / f"{self.source_file.stem}_progress.json"

    @property
    def translations_file(self) -> Path:
        return self.progress_dir / f"{self.source_file.stem}_translations.json"

    def load(self) -> TranslationProgress | None:
        """Load progress from disk (sync)."""
        if not self.progress_file.exists():
            logger.info("No previous progress found")
            return None

        try:
            data = json.loads(self.progress_file.read_text(encoding="utf-8"))
            self._progress = TranslationProgress.from_dict(data)

            current_hash = self._file_hash(self.source_file)
            if self._progress.source_file_hash != current_hash:
                logger.warning("Source file changed, resetting progress")
                return None

            if self.translations_file.exists():
                self._translations = json.loads(self.translations_file.read_text(encoding="utf-8"))

            logger.info(
                f"Resumed: {self._progress.progress_percent:.1f}% "
                f"({self._progress.translated_entries} translated)"
            )
            return self._progress

        except Exception as e:
            logger.error(f"Failed to load progress: {e}")
            return None

    def save(self) -> None:
        """Save progress atomically (sync)."""
        if self._progress is None:
            return

        self._progress.update_timestamp()

        # Atomic write using temp file
        temp_progress = self.progress_file.with_suffix(".tmp")
        temp_translations = self.translations_file.with_suffix(".tmp")

        try:
            temp_progress.write_text(
                json.dumps(self._progress.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_progress.replace(self.progress_file)

            temp_translations.write_text(
                json.dumps(self._translations, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_translations.replace(self.translations_file)

            self._dirty = False

        except Exception as e:
            logger.error(f"Save failed: {e}")
            temp_progress.unlink(missing_ok=True)
            temp_translations.unlink(missing_ok=True)

    def init_new(self, total: int) -> TranslationProgress:
        """Initialize new progress."""
        self._progress = TranslationProgress(
            total_entries=total,
            source_file_hash=self._file_hash(self.source_file),
        )
        self._translations = {}
        self._dirty = True
        self.save()
        return self._progress

    def update(self, entry_id: str, translation: str) -> None:
        """Update single translation."""
        self._translations[entry_id] = translation
        self._dirty = True

    def update_batch(self, translations: dict[str, str]) -> None:
        """Update multiple translations."""
        self._translations.update(translations)
        self._dirty = True

    def get(self, entry_id: str) -> str | None:
        """Get saved translation."""
        return self._translations.get(entry_id)

    def remove(self, entry_id: str) -> None:
        """Remove translation (for retry)."""
        if entry_id in self._translations:
            del self._translations[entry_id]
            self._dirty = True

    @staticmethod
    def _file_hash(path: Path) -> str:
        """Calculate MD5 hash."""
        hasher = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()


@dataclass(slots=True)
class BatchResult:
    """Result of batch translation."""

    batch_idx: int
    translations: dict[str, str]
    success: bool
    error: str = ""
    duration: float = 0.0
    length_warnings: int = 0


def check_translation_length(
    original_en: str,
    original_zh: str,
    translation: str,
    max_ratio: float = 2.0,
) -> tuple[bool, float]:
    """Check if translation length is acceptable."""
    ref_len = max(len(original_en), len(original_zh)) if original_zh else len(original_en)
    if ref_len == 0:
        return True, 1.0

    ratio = len(translation) / ref_len
    return ratio <= max_ratio, ratio


class BatchProcessor:
    """
    Async batch processor with:
    - Parallel batch processing
    - ETA calculation
    - Token counting and cost estimation
    - Graceful Ctrl+C shutdown
    - Verbose mode with detailed output
    - Progress saved after every batch
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        env_config: EnvConfig | None = None,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
        verbose: bool = False,
    ):
        self._config = config or get_config()
        self._env_config = env_config or get_env_config()
        self._llm = llm_client
        self._prompt_builder = prompt_builder
        self._on_progress = progress_callback
        self._log = log_callback or (lambda msg: print(msg))  # Direct print for visibility
        self._verbose = verbose
        self._shutdown_requested = False
        self._semaphore: asyncio.Semaphore | None = None
        self._eta = ETACalculator()
        self._token_counter = TokenCounter(self._config.llm.model)
        self._cost_config = CostConfig(
            price_input=self._env_config.token_price_input,
            price_output=self._env_config.token_price_output,
        )
        self._system_prompt: str = ""  # Cache for token counting

    def _setup_signal_handler(self) -> None:
        """Setup Ctrl+C handler for Windows."""

        def handler(signum, frame):
            self._log("\n[!] Shutdown requested (Ctrl+C)...")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handler)

    async def process(
        self,
        source_csv: Path,
        original_csv: Path,
        output_csv: Path,
        *,
        resume: bool = True,
    ) -> TranslationProgress:
        """Process file with parallel batch translation."""
        self._setup_signal_handler()

        if self._llm is None:
            from .llm_client import LLMClient

            self._llm = LLMClient()

        if self._prompt_builder is None:
            from .llm_client import PromptBuilder

            self._prompt_builder = PromptBuilder(self._config.paths.rules_dir).load()

        self._semaphore = asyncio.Semaphore(self._config.batch.concurrent_requests)

        self._log(f"Loading: {source_csv.name} + {original_csv.name}")
        entries = self._load_entries(source_csv, original_csv)

        if not entries:
            self._log("No entries to translate")
            return TranslationProgress()

        self._log(f"Loaded {len(entries)} entries")

        tracker = ProgressTracker(self._config.paths.progress_dir, source_file=source_csv)

        progress: TranslationProgress | None = None
        if resume:
            progress = tracker.load()
            if progress:
                restored = 0
                for entry in entries:
                    if saved := tracker.get(entry.id):
                        entry.translated = saved
                        entry.status = TranslationStatus.TRANSLATED
                        restored += 1
                self._log(f"Restored {restored} translations from previous session")

                # Check for entries with error markers - they need retry
                retry_count = 0
                for entry in entries:
                    if entry.needs_retry():
                        entry.mark_for_retry()
                        tracker.remove(entry.id)  # Remove from tracker so it gets re-translated
                        retry_count += 1
                        progress.translated_entries -= 1

                if retry_count > 0:
                    self._log(f"Found {retry_count} entries with error markers - will retry")

        if progress is None:
            progress = tracker.init_new(len(entries))

        to_translate = [
            e
            for e in entries
            if e.status == TranslationStatus.PENDING and e.should_translate(self._config.filtering)
        ]

        for entry in entries:
            if entry.status == TranslationStatus.PENDING:
                if not entry.should_translate(self._config.filtering):
                    entry.mark_skipped()
                    progress.skipped_entries += 1

        self._log(f"To translate: {len(to_translate)} (skipped: {progress.skipped_entries})")

        batches = list(self._create_batches(to_translate))
        progress.total_batches = len(batches)
        # Reset batch counter - we're processing fresh batches from to_translate list
        progress.current_batch = 0

        self._log(
            f"Batches: {len(batches)} (size: {self._config.batch.size}, parallel: {self._config.batch.concurrent_requests})"
        )

        self._eta = ETACalculator(total_items=len(to_translate))

        system_prompt = self._prompt_builder.build(
            source_lang=self._config.languages.source,
            original_lang=self._config.languages.original,
            target_lang=self._config.languages.target,
        )
        self._system_prompt = system_prompt
        prompt_tokens = self._token_counter.count_tokens(system_prompt)

        if self._verbose:
            self._log("=" * 60)
            self._log("SYSTEM PROMPT: Loaded (see rules/ folder for details)")
            self._log(f"  Length: {len(system_prompt)} chars, ~{prompt_tokens} tokens")
            if not self._cost_config.is_free:
                self._log(
                    f"  Pricing: ${self._cost_config.price_input}/1M in, ${self._cost_config.price_output}/1M out"
                )
            else:
                self._log("  Pricing: FREE")
            self._log("=" * 60)

        await self._process_all_batches(batches, entries, progress, tracker, system_prompt)

        tracker.save()
        self._save_results(entries, output_csv)

        status = "INTERRUPTED" if self._shutdown_requested else "COMPLETE"
        elapsed = self._eta.format_elapsed()
        token_stats = self._token_counter.stats
        cost_str = token_stats.format_stats(
            self._cost_config.price_input,
            self._cost_config.price_output,
        )

        self._log(f"\n[{status}]")
        self._log(
            f"  Translated: {progress.translated_entries}, Skipped: {progress.skipped_entries}, Errors: {progress.error_entries}"
        )
        self._log(f"  {cost_str}")
        self._log(f"  Elapsed: {elapsed}")

        return progress

    async def _process_all_batches(
        self,
        batches: list[list[TranslationEntry]],
        all_entries: list[TranslationEntry],
        progress: TranslationProgress,
        tracker: ProgressTracker,
        system_prompt: str,
    ) -> None:
        """Process all batches with concurrency control."""

        total_batches = len(batches)
        concurrent = self._config.batch.concurrent_requests

        for group_start in range(0, total_batches, concurrent):
            if self._shutdown_requested:
                self._log("[!] Stopping...")
                break

            group_end = min(group_start + concurrent, total_batches)
            group_batches = [
                (i, batches[i])
                for i in range(group_start, group_end)
                if i >= progress.current_batch
            ]

            if not group_batches:
                continue

            tasks = [
                self._process_single_batch(idx, batch, all_entries, system_prompt)
                for idx, batch in group_batches
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    self._log(f"[ERROR] {result}")
                    continue

                if not isinstance(result, BatchResult):
                    continue

                batch = batches[result.batch_idx]

                if result.success:
                    for entry in batch:
                        if entry.id in result.translations:
                            entry.mark_translated(result.translations[entry.id])
                            progress.translated_entries += 1

                    tracker.update_batch(result.translations)
                    progress.current_batch = result.batch_idx + 1
                else:
                    for entry in batch:
                        entry.mark_error(result.error)
                        progress.error_entries += 1

                self._eta.update(progress.translated_entries)

                pct = progress.progress_percent
                eta_str = self._eta.format_eta()
                elapsed = self._eta.format_elapsed()
                status = "OK" if result.success else "FAIL"
                warn_str = f" [{result.length_warnings} long]" if result.length_warnings else ""

                self._log(
                    f"  Batch {result.batch_idx + 1}/{total_batches}: {status}{warn_str} "
                    f"({result.duration:.1f}s) | "
                    f"{pct:.1f}% | ETA: {eta_str} | Elapsed: {elapsed}"
                )

                if self._on_progress:
                    self._on_progress(progress)

            tracker.save()

            if self._shutdown_requested:
                break

            if self._config.batch.delay_between_batches > 0:
                await asyncio.sleep(self._config.batch.delay_between_batches)

    async def _process_single_batch(
        self,
        batch_idx: int,
        batch: list[TranslationEntry],
        all_entries: list[TranslationEntry],
        system_prompt: str,
    ) -> BatchResult:
        """Process single batch."""

        async with self._semaphore:  # type: ignore
            if self._shutdown_requested:
                return BatchResult(batch_idx, {}, False, "Shutdown")

            start_time = time.time()
            length_warnings = 0

            try:
                ctx_before = self._get_context_before(batch, all_entries)
                ctx_after = self._get_context_after(batch, all_entries)
                texts = [e.to_dict() for e in batch]

                if self._verbose:
                    self._log(f"    [Batch {batch_idx + 1}] Sending {len(texts)} texts:")
                    for i, t in enumerate(texts[:3]):
                        en = t["english"][:50] + "..." if len(t["english"]) > 50 else t["english"]
                        self._log(f"      [{i + 1}] EN: {en}")
                    if len(texts) > 3:
                        self._log(f"      ... +{len(texts) - 3} more")

                user_message = self._build_user_message(texts, ctx_before, ctx_after)
                translations = await self._llm.translate_batch(  # type: ignore
                    texts, system_prompt, ctx_before, ctx_after
                )

                response_text = str(translations)
                input_tokens, output_tokens = self._token_counter.record_batch(
                    self._system_prompt, user_message, response_text
                )

                if self._verbose:
                    self._log(f"      Tokens: in={input_tokens}, out={output_tokens}")

                for entry, translation in zip(batch, translations):
                    is_ok, ratio = check_translation_length(
                        entry.english, entry.original, translation
                    )
                    if not is_ok:
                        length_warnings += 1

                if self._verbose:
                    self._log(
                        f"    [Batch {batch_idx + 1}] Received {len(translations)} translations:"
                    )
                    for i, tr in enumerate(translations[:3]):
                        tr_short = tr[:50] + "..." if len(tr) > 50 else tr
                        self._log(f"      [{i + 1}] RU: {tr_short}")
                    if len(translations) > 3:
                        self._log(f"      ... +{len(translations) - 3} more")

                result_dict = {
                    entry.id: translation for entry, translation in zip(batch, translations)
                }

                duration = time.time() - start_time
                return BatchResult(
                    batch_idx, result_dict, True, duration=duration, length_warnings=length_warnings
                )

            except Exception as e:
                duration = time.time() - start_time
                error_msg = str(e)[:100]
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                return BatchResult(batch_idx, {}, False, error_msg, duration)

    def _load_entries(self, source_csv: Path, original_csv: Path) -> list[TranslationEntry]:
        """Load entries from CSV files."""
        english: dict[str, str] = {}
        with open(source_csv, encoding="utf-8", newline="") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader, None)
            if not header:
                return []

            try:
                id_idx = header.index("ID")
                text_idx = header.index("OriginalText")
            except ValueError:
                logger.error("Required columns not found")
                return []

            for row in reader:
                if len(row) > max(id_idx, text_idx):
                    english[row[id_idx]] = row[text_idx]

        original: dict[str, str] = {}
        if original_csv.exists():
            try:
                with open(original_csv, encoding="utf-8", newline="") as f:
                    reader = csv.reader(f, delimiter=";")
                    header = next(reader, None)
                    if header:
                        try:
                            id_idx = header.index("ID")
                            text_idx = header.index("OriginalText")
                            for row in reader:
                                if len(row) > max(id_idx, text_idx):
                                    original[row[id_idx]] = row[text_idx]
                        except ValueError:
                            pass
            except Exception as e:
                logger.warning(f"Failed to load original: {e}")

        entries = [
            TranslationEntry(
                id=entry_id,
                english=en_text,
                original=original.get(entry_id, ""),
            )
            for entry_id, en_text in english.items()
        ]

        with_context = sum(1 for e in entries if e.original)
        self._log(f"With Chinese context: {with_context}")

        return entries

    def _build_user_message(
        self,
        texts: list[dict[str, str]],
        ctx_before: list[dict[str, str]],
        ctx_after: list[dict[str, str]],
    ) -> str:
        """Build user message for token counting."""
        parts = []

        for item in ctx_before:
            parts.append(f"EN: {item.get('english', '')}")
            if zh := item.get("original"):
                parts.append(f"ZH: {zh}")

        for item in texts:
            parts.append(f"EN: {item.get('english', '')}")
            if zh := item.get("original"):
                parts.append(f"ZH: {zh}")

        for item in ctx_after:
            parts.append(f"EN: {item.get('english', '')}")

        return "\n".join(parts)

    def _create_batches(self, entries: list[TranslationEntry]) -> Iterator[list[TranslationEntry]]:
        """Create batches from entries."""
        batch_size = self._config.batch.size
        for i in range(0, len(entries), batch_size):
            yield entries[i : i + batch_size]

    def _get_context_before(
        self,
        batch: list[TranslationEntry],
        all_entries: list[TranslationEntry],
    ) -> list[dict[str, str]]:
        """Get translated context before batch."""
        if not batch:
            return []

        first_id = batch[0].id
        count = self._config.batch.context_before

        idx = next((i for i, e in enumerate(all_entries) if e.id == first_id), None)

        if idx is None or idx == 0:
            return []

        context = []
        for i in range(max(0, idx - count), idx):
            entry = all_entries[i]
            if entry.status == TranslationStatus.TRANSLATED:
                context.append(
                    {
                        "id": entry.id,
                        "original": entry.original,
                        "english": entry.english,
                        "translated": entry.translated,
                    }
                )

        return context[-count:]

    def _get_context_after(
        self,
        batch: list[TranslationEntry],
        all_entries: list[TranslationEntry],
    ) -> list[dict[str, str]]:
        """Get preview context after batch."""
        if not batch:
            return []

        last_id = batch[-1].id
        count = self._config.batch.context_after

        idx = next((i for i, e in enumerate(all_entries) if e.id == last_id), None)

        if idx is None or idx >= len(all_entries) - 1:
            return []

        return [
            {"id": e.id, "original": e.original, "english": e.english}
            for e in all_entries[idx + 1 : idx + 1 + count]
        ]

    def _save_results(self, entries: list[TranslationEntry], output_csv: Path) -> None:
        """Save results to CSV."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        with open(output_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["ID", "Original", "English", "Russian", "Status"])

            for entry in entries:
                writer.writerow(
                    [
                        entry.id,
                        entry.original,
                        entry.english,
                        entry.translated,
                        str(entry.status),
                    ]
                )

        self._log(f"Saved: {output_csv}")

    def process_sync(
        self,
        source_csv: Path,
        original_csv: Path,
        output_csv: Path,
        *,
        resume: bool = True,
    ) -> TranslationProgress:
        """Synchronous wrapper."""
        return asyncio.run(self.process(source_csv, original_csv, output_csv, resume=resume))
