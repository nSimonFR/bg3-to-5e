"""LSPK v12/v13 archive parser for BG3 .lsv save files.

LSV files are LSPK (Larian Studio PacKage) archives containing:
- meta.lsf: Save metadata
- Globals.lsf: Game state including character data (NewAge format)
- Various other .lsf files for regions, items, etc.

Format based on LSLib: https://github.com/Norbyte/lslib
"""

import json
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import BinaryIO

import lz4.block
import zstandard as zstd


class LSPKVersion(IntEnum):
    """LSPK package versions."""
    V15 = 15  # BG3 format
    V16 = 16  # BG3 Patch 3+
    V18 = 18  # BG3 newer patches


class CompressionMethod(IntEnum):
    """Compression methods used in LSPK."""
    NONE = 0
    ZLIB = 1
    LZ4 = 2
    ZSTD = 3


@dataclass
class LSPKHeader:
    """LSPK package header."""
    version: int
    file_list_offset: int
    file_list_size: int
    flags: int
    priority: int
    md5: bytes
    num_parts: int


@dataclass
class FileEntry:
    """A file entry in the LSPK archive."""
    name: str
    offset_in_file: int
    size_on_disk: int
    uncompressed_size: int
    archive_part: int
    flags: int
    crc: int

    @property
    def compression_method(self) -> CompressionMethod:
        """Get compression method from flags."""
        return CompressionMethod((self.flags >> 4) & 0x0F)

    @property
    def is_compressed(self) -> bool:
        """Check if file is compressed."""
        return self.compression_method != CompressionMethod.NONE


@dataclass
class SavePartyMember:
    """Character data from SaveInfo.json."""
    name: str  # Origin name or "Player" for custom
    race: str
    level: int
    classes: list[dict[str, str]]  # [{"Main": "Bard", "Sub": ""}]
    xp_total: int
    xp_current_level: int
    origin: str
    is_player: bool  # True if Origin == "Generic" (custom character)

    # Stats populated from NewAge/LSMF blob (if available)
    ability_scores: dict[str, int] | None = None
    hp: int | None = None
    max_hp: int | None = None
    proficiency_bonus: int | None = None
    spells: list[str] | None = None
    background: str | None = None
    deity: str | None = None
    level_ups: list[dict] | None = None  # [{class_uuid, subclass_uuid}, ...]
    action_resources: list[dict] | None = None  # [{uuid, current, max, level}, ...]
    skill_proficiencies: dict[str, int] | None = None  # {skill_name: 1|2}
    passives: list[str] | None = None  # passive names from save data
    gold: int | None = None  # gold pieces from inventory


@dataclass
class LSVSaveInfo:
    """Basic information about an LSV save file."""
    path: Path
    character_name: str | None
    save_name: str | None
    timestamp: str | None
    level: int | None
    files: list[str]
    party: list[SavePartyMember] | None = None


class LSVParser:
    """Parser for BG3 .lsv save files (LSPK format)."""

    MAGIC_LSPK = b"LSPK"
    MAGIC_LSF = b"LSOF"

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.header: LSPKHeader | None = None
        self.files: dict[str, FileEntry] = {}
        self._file_handle: BinaryIO | None = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self) -> None:
        """Open the LSV file and parse the header."""
        self._file_handle = open(self.path, "rb")
        self._parse_header()
        self._parse_file_list()

    def close(self) -> None:
        """Close the file handle."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def _parse_header(self) -> None:
        """Parse the LSPK header."""
        if not self._file_handle:
            raise RuntimeError("File not open")

        # Read magic
        magic = self._file_handle.read(4)
        if magic != self.MAGIC_LSPK:
            raise ValueError(f"Invalid LSPK magic: {magic!r}")

        # Read version
        version = struct.unpack("<I", self._file_handle.read(4))[0]

        if version >= LSPKVersion.V18:
            self._parse_header_v18()
        elif version >= LSPKVersion.V15:
            self._parse_header_v15()
        else:
            raise ValueError(f"Unsupported LSPK version: {version}")

    def _parse_header_v15(self) -> None:
        """Parse LSPK v15/v16 header."""
        if not self._file_handle:
            raise RuntimeError("File not open")

        self._file_handle.seek(0)
        data = self._file_handle.read(22)

        (
            _magic,
            version,
            file_list_offset,
            file_list_size,
            flags,
            priority,
        ) = struct.unpack("<4sIQIBB", data[:22])

        md5 = self._file_handle.read(16)

        self.header = LSPKHeader(
            version=version,
            file_list_offset=file_list_offset,
            file_list_size=file_list_size,
            flags=flags,
            priority=priority,
            md5=md5,
            num_parts=1,
        )

    def _parse_header_v18(self) -> None:
        """Parse LSPK v18 header."""
        if not self._file_handle:
            raise RuntimeError("File not open")

        self._file_handle.seek(0)
        data = self._file_handle.read(40)

        (
            _magic,
            version,
            file_list_offset,
            file_list_size,
            flags,
            priority,
            md5,
            num_parts,
        ) = struct.unpack("<4sIQIBB16sH", data[:40])

        self.header = LSPKHeader(
            version=version,
            file_list_offset=file_list_offset,
            file_list_size=file_list_size,
            flags=flags,
            priority=priority,
            md5=md5,
            num_parts=num_parts,
        )

    def _parse_file_list(self) -> None:
        """Parse the file list from the LSPK archive."""
        if not self._file_handle or not self.header:
            raise RuntimeError("Header not parsed")

        self._file_handle.seek(self.header.file_list_offset)
        file_list_data = self._file_handle.read(self.header.file_list_size)

        if self.header.version >= LSPKVersion.V18:
            self._parse_file_list_v18(file_list_data)
        else:
            self._parse_file_list_legacy(file_list_data)

    def _parse_file_list_v18(self, file_list_data: bytes) -> None:
        """Parse v18 file list.

        V18 format:
        - uint32: numFiles
        - uint32: compressedStringTableSize
        - [compressedStringTableSize bytes]: LZ4-compressed entry table

        The decompressed entry table has 272-byte records per file:
        - 256 bytes: null-padded filename
        - 16 bytes: entry metadata (offset, archive part, flags, sizes)
        """
        num_files = struct.unpack("<I", file_list_data[:4])[0]
        string_buf_size = struct.unpack("<I", file_list_data[4:8])[0]
        string_buf = file_list_data[8:8 + string_buf_size]

        ENTRY_SIZE = 272
        NAME_SIZE = 256

        # Decompress the entry table (LZ4 compressed)
        try:
            decompressed = lz4.block.decompress(
                string_buf,
                uncompressed_size=num_files * ENTRY_SIZE,
            )
        except Exception:
            # Fallback: try zstd
            try:
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(
                    string_buf, max_output_size=num_files * ENTRY_SIZE
                )
            except Exception:
                return

        for i in range(num_files):
            record = decompressed[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE]
            if len(record) < ENTRY_SIZE:
                break

            # Parse filename (256 bytes, null-padded)
            name_bytes = record[:NAME_SIZE]
            null_pos = name_bytes.index(0) if 0 in name_bytes else NAME_SIZE
            name = name_bytes[:null_pos].decode("utf-8", errors="replace")

            # Parse metadata (16 bytes after filename)
            meta = record[NAME_SIZE:]
            offset_lo = struct.unpack("<I", meta[0:4])[0]
            offset_hi = struct.unpack("<H", meta[4:6])[0]
            full_offset = offset_lo | (offset_hi << 32)
            archive_part = meta[6]
            entry_flags = meta[7]
            size_on_disk = struct.unpack("<I", meta[8:12])[0]
            uncompressed_size = struct.unpack("<I", meta[12:16])[0]

            self.files[name] = FileEntry(
                name=name,
                offset_in_file=full_offset,
                size_on_disk=size_on_disk,
                uncompressed_size=uncompressed_size,
                archive_part=archive_part,
                flags=entry_flags,
                crc=0,
            )

    def _parse_file_list_legacy(self, file_list_data: bytes) -> None:
        """Parse pre-v18 file list (may be compressed)."""
        compression = self.header.flags & 0x0F if self.header else 0
        decompressed = None

        # Check for zstd magic first
        if file_list_data[:4] == b'\x28\xb5\x2f\xfd':
            try:
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(file_list_data)
            except Exception:
                pass

        if decompressed is None and compression == 2:  # LZ4
            try:
                uncompressed_size = struct.unpack("<I", file_list_data[:4])[0]
                decompressed = lz4.block.decompress(
                    file_list_data[4:],
                    uncompressed_size=uncompressed_size
                )
            except Exception:
                pass

        if decompressed is not None:
            self._parse_file_entries(decompressed)
        else:
            self._parse_file_entries(file_list_data)

    def _parse_file_entries(self, data: bytes) -> None:
        """Parse file entries from legacy (pre-v18) file list."""
        if len(data) < 8:
            return

        num_files = struct.unpack("<I", data[:4])[0]
        self._parse_legacy_entries(data, num_files)

    def _parse_legacy_entries(self, data: bytes, num_files: int) -> None:
        """Parse legacy format file entries."""
        offset = 4  # Skip num_files

        for _ in range(num_files):
            if offset + 4 > len(data):
                break

            # Name length (2 bytes) + name + entry data
            name_len = struct.unpack("<H", data[offset:offset + 2])[0]
            offset += 2

            name = data[offset:offset + name_len].decode("utf-8", errors="replace")
            offset += name_len

            # Entry data: 32 bytes
            if offset + 32 > len(data):
                break

            entry_data = struct.unpack("<QQIIII", data[offset:offset + 32])
            offset += 32

            entry = FileEntry(
                name=name,
                offset_in_file=entry_data[0],
                size_on_disk=entry_data[1] & 0xFFFFFFFF,
                uncompressed_size=(entry_data[1] >> 32) & 0xFFFFFFFF,
                archive_part=entry_data[2],
                flags=entry_data[3],
                crc=entry_data[4],
            )

            self.files[name] = entry

    def extract_file(self, name: str) -> bytes:
        """Extract a file from the archive."""
        if not self._file_handle:
            raise RuntimeError("File not open")

        if name not in self.files:
            raise KeyError(f"File not found in archive: {name}")

        entry = self.files[name]
        if entry.size_on_disk == 0:
            raise ValueError(f"File entry has no size data: {name}")

        self._file_handle.seek(entry.offset_in_file)
        data = self._file_handle.read(entry.size_on_disk)

        # If sizes match and no compression indicated, return raw
        if entry.size_on_disk == entry.uncompressed_size and not entry.is_compressed:
            return data

        # Auto-detect compression from magic bytes (v18 flags can be unreliable)
        if data[:4] == b'\x28\xb5\x2f\xfd':  # zstd magic
            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(data, max_output_size=entry.uncompressed_size)

        # Try LZ4
        try:
            return lz4.block.decompress(
                data,
                uncompressed_size=entry.uncompressed_size,
            )
        except Exception:
            pass

        # Fallback: return raw data
        return data

    def list_files(self) -> list[str]:
        """List all files in the archive."""
        return list(self.files.keys())

    def extract_newage_stats(self):
        """Extract character stats from the NewAge (LSMF) blob in Globals.lsf.

        Returns a list of NewAgeCharacterStats or None if extraction fails.
        """
        if "Globals.lsf" not in self.files:
            return None

        try:
            from .lsf_parser import LSFParser
            from .newage_parser import NewAgeParser

            globals_data = self.extract_file("Globals.lsf")
            lsf = LSFParser(globals_data)
            blob = lsf.get_newage_blob()
            if not blob:
                return None

            na = NewAgeParser(blob)
            return na.parse()
        except Exception:
            return None

    def get_save_info(self) -> LSVSaveInfo:
        """Get information about the save, including party data from SaveInfo.json."""
        character_name = None
        save_name = None
        timestamp = None
        level = None
        party = None

        # Try to extract SaveInfo.json (contains class, level, race for all party members)
        if "SaveInfo.json" in self.files:
            try:
                data = self.extract_file("SaveInfo.json")
                # Some saves have zlib-compressed SaveInfo.json
                if data[:2] == b'\x78\x9c' or data[:2] == b'\x78\x01':
                    import zlib
                    data = zlib.decompress(data)
                save_json = json.loads(data.decode("utf-8"))
                save_name = save_json.get("Save Name")

                # Parse party members
                active_party = save_json.get("Active Party", {})
                characters = active_party.get("Characters", [])
                party = []
                for char in characters:
                    origin = char.get("Origin", "Generic")
                    is_player = origin == "Generic"
                    member = SavePartyMember(
                        name=origin if not is_player else "Player",
                        race=char.get("Race", "Unknown"),
                        level=char.get("Level", 1),
                        classes=char.get("Classes", []),
                        xp_total=char.get("Experience Points (Total)", 0),
                        xp_current_level=char.get("Experience Points (Current level)", 0),
                        origin=origin,
                        is_player=is_player,
                    )
                    party.append(member)
                    # First player character's level is the main level
                    if is_player and level is None:
                        level = member.level
            except Exception:
                pass

        # Try meta.lsf for additional metadata (always parse for character name)
        if "meta.lsf" in self.files:
            try:
                from .lsf_parser import LSFParser
                meta_data = self.extract_file("meta.lsf")
                parser = LSFParser(meta_data)
                parser._parse_header()
                if parser.header and parser.header.version >= 2:
                    parser._decompress_sections()
                    parser._parse_string_table()
                    parser._parse_nodes_raw()
                    parser._parse_attributes_raw()

                    # Extract LeaderName directly from attributes
                    for attr in parser.attributes:
                        if attr["name"] == "LeaderName":
                            off = attr["value_offset"]
                            length = attr.get("length", 0)
                            if length > 0 and off + length <= len(parser.values):
                                raw = parser.values[off:off + length]
                                name = raw.decode("utf-8", errors="replace").rstrip("\x00")
                                if name and len(name) >= 2 and name.isascii():
                                    character_name = name
                            break
            except Exception:
                pass

        # Get character name from folder path
        # BG3 folders: CharacterName-Timestamp__SaveType_N
        if not character_name:
            folder_name = self.path.parent.name
            if "-" in folder_name:
                potential_name = folder_name.split("-")[0]
                if potential_name and potential_name not in ["AutoSave", "QuickSave"]:
                    character_name = potential_name

        # Final fallback: filename
        if not character_name:
            stem = self.path.stem
            parts = stem.split("-")
            if parts and parts[0] not in ["AutoSave", "QuickSave"]:
                character_name = parts[0]

        return LSVSaveInfo(
            path=self.path,
            character_name=character_name,
            save_name=save_name,
            timestamp=timestamp,
            level=level,
            files=self.list_files(),
            party=party,
        )


def list_saves(save_dir: Path | str) -> list[LSVSaveInfo]:
    """List all save files in a directory with their info."""
    save_dir = Path(save_dir)
    saves = []

    for lsv_file in sorted(save_dir.glob("**/*.lsv")):
        try:
            with LSVParser(lsv_file) as parser:
                saves.append(parser.get_save_info())
        except Exception as e:
            # Add with minimal info on parse error
            saves.append(LSVSaveInfo(
                path=lsv_file,
                character_name=lsv_file.stem.split("-")[0] if "-" in lsv_file.stem else None,
                save_name=lsv_file.stem,
                timestamp=None,
                level=None,
                files=[],
            ))

    return saves
