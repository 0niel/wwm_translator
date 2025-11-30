from __future__ import annotations

import csv
import logging
import struct
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self

import pyzstd

from .models import ExtractionResult, TextEntry


logger = logging.getLogger(__name__)

LogCallback = Callable[[str], None]
BytesReader = Generator[bytes, None, None]


class Extractor(Protocol):
    def extract(self, input_path: Path, output_path: Path) -> ExtractionResult: ...


ARCHIVE_MAGIC = b"\xef\xbe\xad\xde"  # 0xDEADBEEF
TEXT_MAGIC = b"\xdc\x96\x58\x59"


@dataclass(slots=True, frozen=True)
class ArchiveHeader:
    """Archive header: Magic(4) + Version(4) + BlockCount(4)."""
    version: int = 1
    offset_count: int = 0

    @classmethod
    def read(cls, data: bytes) -> Self | None:
        if len(data) < 12 or data[:4] != ARCHIVE_MAGIC:
            return None
        version = struct.unpack("<I", data[4:8])[0]
        offset_count = struct.unpack("<I", data[8:12])[0] + 1
        return cls(version=version, offset_count=offset_count)


@dataclass(slots=True)
class BlockHeader:
    """Compressed block header: Type(1) + CompSize(4) + DecompSize(4)."""
    compression_type: int
    compressed_size: int
    decompressed_size: int

    @classmethod
    def read(cls, data: bytes) -> Self | None:
        if len(data) < 9:
            return None
        comp_type, comp_size, decomp_size = struct.unpack("<BII", data[:9])
        return cls(compression_type=comp_type, compressed_size=comp_size, decompressed_size=decomp_size)

    @property
    def is_zstd(self) -> bool:
        return self.compression_type == 0x04


class BinaryExtractor:
    """Game archive extractor (ZSTD compressed blocks)."""

    __slots__ = ("_log",)

    def __init__(self, log_callback: LogCallback | None = None):
        self._log = log_callback or logger.info

    def extract(self, input_file: Path, output_dir: Path) -> ExtractionResult:
        errors: list[str] = []
        files_count = 0

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            base_name = input_file.stem

            with open(input_file, "rb") as f:
                header_data = f.read(12)
                header = ArchiveHeader.read(header_data)

                if header is None:
                    return ExtractionResult.fail(f"Invalid archive: {input_file}")

                if header.offset_count == 1:
                    files_count = self._extract_single(f, output_dir, base_name)
                else:
                    files_count, errors = self._extract_multiple(f, output_dir, base_name, header.offset_count)

            return ExtractionResult.ok(f"Extracted {files_count} files", files=files_count)

        except Exception as e:
            logger.exception("Archive extraction failed")
            return ExtractionResult.fail(str(e), errors)

    def _extract_single(self, f, output_dir: Path, base_name: str) -> int:
        comp_block_len = struct.unpack("<I", f.read(4))[0]
        comp_block = f.read(comp_block_len)

        block_header = BlockHeader.read(comp_block[:9])
        if block_header is None or not block_header.is_zstd:
            return 0

        decomp_data = pyzstd.decompress(comp_block[9:])
        output_path = output_dir / f"{base_name}_0.dat"
        output_path.write_bytes(decomp_data)

        self._log(f"Extracted: {output_path.name}")
        return 1

    def _extract_multiple(self, f, output_dir: Path, base_name: str, offset_count: int) -> tuple[int, list[str]]:
        errors: list[str] = []
        count = 0

        offsets = [struct.unpack("<I", f.read(4))[0] for _ in range(offset_count)]
        data_start = f.tell()

        for i in range(offset_count - 1):
            block_len = offsets[i + 1] - offsets[i]
            f.seek(data_start + offsets[i])
            comp_block = f.read(block_len)

            block_header = BlockHeader.read(comp_block[:9])
            if block_header is None or not block_header.is_zstd:
                continue

            try:
                decomp_data = pyzstd.decompress(comp_block[9:])
                output_path = output_dir / f"{base_name}_{i}.dat"
                output_path.write_bytes(decomp_data)
                count += 1
                self._log(f"Extracted: {output_path.name}")
            except Exception as e:
                errors.append(f"Block {i}: {e}")

        return count, errors

    def pack(self, input_dir: Path, output_file: Path) -> ExtractionResult:
        import re

        try:
            dat_files = sorted(
                input_dir.glob("*.dat"),
                key=lambda x: int(m.group(1)) if (m := re.search(r"(\d+)\.dat$", x.name)) else float("inf"),
            )

            if not dat_files:
                return ExtractionResult.fail("No .dat files to pack")

            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "wb") as outfile:
                outfile.write(ARCHIVE_MAGIC)
                outfile.write(b"\x01\x00\x00\x00")
                outfile.write(struct.pack("<I", len(dat_files)))

                archive_data = b""

                for dat_file in dat_files:
                    file_data = dat_file.read_bytes()
                    comp_data = pyzstd.compress(file_data)

                    header = struct.pack("<BII", 4, len(comp_data), len(file_data))
                    outfile.write(struct.pack("<I", len(archive_data)))
                    archive_data += header + comp_data

                    self._log(f"Packed: {dat_file.name}")

                outfile.write(struct.pack("<I", len(archive_data)))
                outfile.write(archive_data)

            return ExtractionResult.ok(f"Packed {len(dat_files)} files", files=len(dat_files))

        except Exception as e:
            logger.exception("Packing failed")
            return ExtractionResult.fail(str(e))


class TextExtractor:
    """Text extractor from .dat files (legacy format with TEXT_MAGIC)."""

    __slots__ = ("_log",)

    def __init__(self, log_callback: LogCallback | None = None):
        self._log = log_callback or logger.info

    def extract(self, input_dir: Path, output_file: Path) -> ExtractionResult:
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)

            dat_files = sorted(input_dir.glob("*.dat"))
            if not dat_files:
                return ExtractionResult.fail("No .dat files found")

            total_texts = 0

            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(TextEntry.csv_header())

                for dat_file in dat_files:
                    entries = list(self._extract_from_dat(dat_file, total_texts))

                    for entry in entries:
                        writer.writerow(entry.to_csv_row())
                        total_texts += 1

                    if entries:
                        self._log(f"Processed: {dat_file.name} ({len(entries)} rows)")

            return ExtractionResult.ok(f"Extracted {total_texts} texts", texts=total_texts)

        except Exception as e:
            logger.exception("Text extraction failed")
            return ExtractionResult.fail(str(e))

    def _extract_from_dat(self, dat_file: Path, start_number: int) -> Iterator[TextEntry]:
        try:
            with open(dat_file, "rb") as f:
                f.seek(16)
                if f.read(4) != TEXT_MAGIC:
                    return

                f.seek(0)
                count_full = struct.unpack("<I", f.read(4))[0]
                f.read(4)
                count_text = struct.unpack("<I", f.read(4))[0]
                f.read(12)

                code = f.read(count_full).hex()
                f.read(17)
                data_start = f.tell()

                for i in range(count_full):
                    f.seek(data_start + (i * 16))
                    text_id = f.read(8).hex()
                    start_text_offset = f.tell()
                    offset_text = struct.unpack("<I", f.read(4))[0]
                    length = struct.unpack("<I", f.read(4))[0]

                    f.seek(start_text_offset + offset_text)
                    text = f.read(length).decode("utf-8", errors="ignore")
                    text = text.replace("\n", "\\n").replace("\r", "\\r")

                    yield TextEntry(
                        number=start_number + i + 1,
                        file_name=dat_file.name,
                        all_blocks=count_full,
                        work_blocks=count_text,
                        current_block=i,
                        unknown=code[i * 2 : (i + 1) * 2],
                        text_id=text_id,
                        original_text=text,
                    )

        except Exception as e:
            logger.warning(f"Error reading {dat_file}: {e}")

    def pack(self, csv_file: Path, output_dir: Path) -> ExtractionResult:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            entries_by_file: dict[str, list[TextEntry]] = {}

            with open(csv_file, encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader)

                for row in reader:
                    if len(row) < 8:
                        continue
                    entry = TextEntry.from_csv_row(row)
                    entries_by_file.setdefault(entry.file_name, []).append(entry)

            files_count = 0
            for file_name, entries in entries_by_file.items():
                output_path = output_dir / file_name
                self._pack_to_dat(entries, output_path)
                files_count += 1
                self._log(f"Packed: {file_name}")

            return ExtractionResult.ok(f"Packed {files_count} files", files=files_count)

        except Exception as e:
            logger.exception("Text packing failed")
            return ExtractionResult.fail(str(e))

    def _pack_to_dat(self, entries: list[TextEntry], output_path: Path) -> None:
        if not entries:
            return

        first = entries[0]
        all_blocks = first.all_blocks
        work_blocks = first.work_blocks

        all_blocks_bytes = struct.pack("<II", all_blocks, 0)
        work_blocks_bytes = struct.pack("<II", work_blocks, 0)
        file_bytes = TEXT_MAGIC + b"\x00\x00\x00\x00"

        start_unk = len(all_blocks_bytes) + len(work_blocks_bytes) + len(file_bytes)
        start_id = start_unk + all_blocks + 17
        curr_text = start_id + all_blocks * 16

        filled_bytes_unk = b""
        filled_bytes_id = b""
        filled_bytes_text = b""

        for entry in entries:
            text = entry.original_text.replace("\\n", "\x0a").replace("\\r", "\x0d")
            text_encoded = text.encode("utf-8")

            unk_byte = bytes.fromhex(entry.unknown)
            filled_bytes_unk += unk_byte
            start_unk += 1

            if start_unk >= all_blocks + 24:
                if len(filled_bytes_unk) >= 16:
                    filled_bytes_unk += b"\xff" + filled_bytes_unk[:16]
                else:
                    filled_bytes_unk += b"\xff" + filled_bytes_unk + b"\x80" * (16 - len(filled_bytes_unk))

            id_byte = bytes.fromhex(entry.text_id)
            filled_bytes_id += id_byte
            start_id += 8

            offset_len = struct.pack("<II", curr_text - start_id, len(text_encoded))
            filled_bytes_id += offset_len
            start_id += 8

            filled_bytes_text += text_encoded
            curr_text += len(text_encoded)

        with open(output_path, "wb") as f:
            f.write(all_blocks_bytes)
            f.write(work_blocks_bytes)
            f.write(file_bytes)
            f.write(filled_bytes_unk)
            f.write(filled_bytes_id)
            f.write(filled_bytes_text)


def extract_game_locale(
    locale_file: Path,
    output_base_dir: Path,
    log_callback: LogCallback | None = None,
) -> ExtractionResult:
    """Full extraction pipeline: archive -> .dat files -> CSV."""
    lang_code = locale_file.name.replace("translate_words_map_", "")
    dat_dir = output_base_dir / "dat" / lang_code
    csv_file = output_base_dir / "csv" / f"{lang_code}.csv"

    binary_extractor = BinaryExtractor(log_callback)
    archive_result = binary_extractor.extract(locale_file, dat_dir)

    if not archive_result.success:
        return archive_result

    text_extractor = TextExtractor(log_callback)
    text_result = text_extractor.extract(dat_dir, csv_file)

    if not text_result.success:
        return text_result

    return ExtractionResult.ok(
        f"Extracted {archive_result.files_extracted} files, {text_result.texts_extracted} texts",
        files=archive_result.files_extracted,
        texts=text_result.texts_extracted,
    )
