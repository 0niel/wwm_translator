from __future__ import annotations

import csv
import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .models import ExtractionResult, TextEntry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HashMapHeader:
    """24-byte header: Int64 EntryCount, Int64 ValueCount, Int32 Timestamp, Int32 Padding."""
    entry_count: int
    value_count: int
    timestamp: int
    padding: int = 0
    
    @classmethod
    def read(cls, data: bytes) -> "HashMapHeader":
        entry_count = struct.unpack('<Q', data[:8])[0]
        value_count = struct.unpack('<Q', data[8:16])[0]
        timestamp = struct.unpack('<I', data[16:20])[0]
        padding = struct.unpack('<I', data[20:24])[0]
        return cls(entry_count, value_count, timestamp, padding)
    
    def to_bytes(self) -> bytes:
        return struct.pack('<QQII', self.entry_count, self.value_count, self.timestamp, self.padding)


@dataclass(slots=True)
class TableEntry:
    """Entry: 8-byte hash + Int32 RelativeOffset + Int32 TextLength."""
    hash_id: bytes
    relative_offset: int
    text_length: int
    text: str = ""
    
    @property
    def id_hex(self) -> str:
        return self.hash_id.hex()


class HashMapDatFile:
    """Parser/Writer for HashMap .dat files. Preserves bucket structure."""
    
    __slots__ = ('header', 'buckets', 'entries', 'raw_data', 'bucket_end_offset')
    
    def __init__(self):
        self.header: HashMapHeader | None = None
        self.buckets: bytes = b''
        self.entries: list[TableEntry] = []
        self.raw_data: bytes = b''
        self.bucket_end_offset: int = 0
    
    def read(self, data: bytes) -> bool:
        if len(data) < 24:
            return False
        
        self.raw_data = data
        self.header = HashMapHeader.read(data[:24])
        entry_count = self.header.entry_count
        
        if entry_count == 0:
            self.buckets = data[24:]
            return True
        
        # Detect bucket size
        bucket_candidates = [64, 128, 32, 256, 16]
        
        for bucket_count in bucket_candidates:
            bucket_size = bucket_count * 8
            entries_start = 24 + bucket_size
            
            if entries_start + entry_count * 16 > len(data):
                continue
            
            valid = True
            for i in range(min(3, entry_count)):
                entry_offset = entries_start + i * 16
                if entry_offset + 16 > len(data):
                    valid = False
                    break
                    
                pot_offset = struct.unpack('<I', data[entry_offset + 8:entry_offset + 12])[0]
                pot_length = struct.unpack('<I', data[entry_offset + 12:entry_offset + 16])[0]
                
                text_pos = entry_offset + 8 + pot_offset
                if text_pos < 0 or text_pos + pot_length > len(data):
                    valid = False
                    break
            
            if valid:
                self.bucket_end_offset = entries_start
                self.buckets = data[24:entries_start]
                break
        
        if not self.buckets:
            self.bucket_end_offset = 24 + 512
            self.buckets = data[24:self.bucket_end_offset]
        
        entries_start = self.bucket_end_offset
        self.entries = []
        
        for i in range(entry_count):
            entry_offset = entries_start + i * 16
            if entry_offset + 16 > len(data):
                break
                
            hash_id = data[entry_offset:entry_offset + 8]
            relative_offset = struct.unpack('<I', data[entry_offset + 8:entry_offset + 12])[0]
            text_length = struct.unpack('<I', data[entry_offset + 12:entry_offset + 16])[0]
            
            text_pos = entry_offset + 8 + relative_offset
            
            text = ""
            if text_length > 0 and text_pos + text_length <= len(data):
                text = data[text_pos:text_pos + text_length].decode('utf-8', errors='ignore')
            
            self.entries.append(TableEntry(hash_id, relative_offset, text_length, text))
        
        return True
    
    def write(self, translations: dict[str, str] | None = None) -> bytes:
        """Write .dat file, optionally replacing texts by hash_id_hex -> new_text."""
        if not self.header or not self.entries:
            return self.raw_data
        
        if translations:
            for entry in self.entries:
                if entry.id_hex in translations:
                    entry.text = translations[entry.id_hex]
        
        entries_start = 24 + len(self.buckets)
        
        text_data = b''
        text_positions: list[tuple[int, int]] = []
        
        for i, entry in enumerate(self.entries):
            entry_offset = entries_start + i * 16
            text_encoded = entry.text.encode('utf-8')
            
            text_pos = entries_start + len(self.entries) * 16 + len(text_data)
            relative_offset = text_pos - (entry_offset + 8)
            
            text_positions.append((relative_offset, len(text_encoded)))
            text_data += text_encoded
        
        entries_data = b''
        for i, entry in enumerate(self.entries):
            rel_off, length = text_positions[i]
            entries_data += entry.hash_id
            entries_data += struct.pack('<II', rel_off, length)
        
        self.header.value_count = len(self.entries)
        
        return self.header.to_bytes() + self.buckets + entries_data + text_data
    
    def get_text_entries(self, file_name: str, start_number: int = 0) -> Iterator[TextEntry]:
        if not self.header:
            return
            
        for i, entry in enumerate(self.entries):
            text = entry.text.replace('\n', '\\n').replace('\r', '\\r')
            yield TextEntry(
                number=start_number + i + 1,
                file_name=file_name,
                all_blocks=self.header.entry_count,
                work_blocks=self.header.value_count,
                current_block=i,
                unknown="00",
                text_id=entry.id_hex,
                original_text=text,
            )


class HashMapTextExtractor:
    """Text extractor using HashMap format."""
    
    def __init__(self, log_callback=None):
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
                    parser = HashMapDatFile()
                    data = dat_file.read_bytes()
                    
                    if not parser.read(data):
                        self._log(f"Skipped (invalid): {dat_file.name}")
                        continue
                    
                    entries = list(parser.get_text_entries(dat_file.name, total_texts))
                    
                    for entry in entries:
                        if entry.original_text:
                            writer.writerow(entry.to_csv_row())
                            total_texts += 1
                    
                    if entries:
                        self._log(f"Processed: {dat_file.name} ({len(entries)} entries)")
            
            return ExtractionResult.ok(f"Extracted {total_texts} texts", texts=total_texts)
            
        except Exception as e:
            logger.exception("Text extraction failed")
            return ExtractionResult.fail(str(e))
    
    def pack(self, csv_file: Path, source_dat_dir: Path, output_dir: Path) -> ExtractionResult:
        """Pack translations: reads original .dat files, applies translations, preserves structure."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            translations: dict[str, dict[str, str]] = {}
            
            with open(csv_file, encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader)
                
                for row in reader:
                    if len(row) < 8:
                        continue
                    file_name = row[1]
                    text_id = row[6]
                    text = row[7].replace('\\n', '\n').replace('\\r', '\r')
                    
                    if file_name not in translations:
                        translations[file_name] = {}
                    translations[file_name][text_id] = text
            
            files_count = 0
            
            for dat_file in sorted(source_dat_dir.glob("*.dat")):
                parser = HashMapDatFile()
                data = dat_file.read_bytes()
                
                if not parser.read(data):
                    (output_dir / dat_file.name).write_bytes(data)
                    files_count += 1
                    continue
                
                file_translations = translations.get(dat_file.name, {})
                new_data = parser.write(file_translations) if file_translations else data
                
                (output_dir / dat_file.name).write_bytes(new_data)
                files_count += 1
                self._log(f"Packed: {dat_file.name}")
            
            return ExtractionResult.ok(f"Packed {files_count} files", files=files_count)
            
        except Exception as e:
            logger.exception("Packing failed")
            return ExtractionResult.fail(str(e))

