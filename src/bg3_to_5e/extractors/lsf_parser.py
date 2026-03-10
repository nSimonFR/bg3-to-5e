"""LSF (Larian Save Format) binary parser.

LSF files contain structured data in a binary format. This parser handles
versions 1-7, including the BG3 v7 format with LZ4 frame compression
and hash-table string names.

Based on LSLib: https://github.com/Norbyte/lslib
"""

import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import lz4.block
import lz4.frame
import zstandard as zstd


class LSFVersion(IntEnum):
    """LSF format versions."""
    V1 = 1  # Initial
    V2 = 2  # Chunked compression
    V3 = 3  # Extended nodes (V3 format)
    V4 = 4  # BG3
    V5 = 5  # BG3 extended header (Int64 engine version)
    V6 = 6  # BG3 node keys (MetadataV6 with Keys fields)
    V7 = 7  # BG3 Patch 3


class NodeAttribute(IntEnum):
    """LSF attribute data types (matching LSLib numbering)."""
    NONE = 0
    BYTE = 1
    SHORT = 2
    USHORT = 3
    INT = 4
    UINT = 5
    FLOAT = 6
    DOUBLE = 7
    IVEC2 = 8
    IVEC3 = 9
    IVEC4 = 10
    VEC2 = 11
    VEC3 = 12
    VEC4 = 13
    MAT2 = 14
    MAT3 = 15
    MAT3X4 = 16
    MAT4X3 = 17
    MAT4 = 18
    BOOL = 19
    STRING = 20
    PATH = 21
    FIXEDSTRING = 22
    LSSTRING = 23
    UINT64 = 24
    SCRATCHBUFFER = 25
    LONG = 26
    INT8 = 27
    TRANSLATEDSTRING = 28
    WSTRING = 29
    LSWSTRING = 30
    UUID = 31
    INT64 = 32
    TRANSLATEDFSSTRING = 33


class MetadataFormat(IntEnum):
    """LSF metadata format (determines V2 vs V3 node/attribute layout)."""
    NONE = 0
    KEYS_AND_ADJACENCY = 1
    NONE2 = 2


@dataclass
class LSFHeader:
    """LSF file header (all versions)."""
    magic: bytes
    version: int
    engine_version: int
    strings_uncompressed_size: int
    strings_size_on_disk: int
    keys_uncompressed_size: int
    keys_size_on_disk: int
    nodes_uncompressed_size: int
    nodes_size_on_disk: int
    attributes_uncompressed_size: int
    attributes_size_on_disk: int
    values_uncompressed_size: int
    values_size_on_disk: int
    compression_flags: int
    metadata_format: MetadataFormat


class LSFParser:
    """Parser for LSF binary files."""

    MAGIC = b"LSOF"

    def __init__(self, data: bytes):
        # Some saves have zlib-compressed LSF files
        if data[:2] in (b'\x78\x9c', b'\x78\x01', b'\x78\xda'):
            import zlib
            data = zlib.decompress(data)
        self.data = data
        self.offset = 0
        self.header: LSFHeader | None = None
        self.names: list[list[str]] = []  # Hash table: list of chains
        self.nodes: list[dict] = []
        self.attributes: list[dict] = []
        self.values: bytes = b""

    def parse(self) -> dict[str, Any]:
        """Parse the LSF data and return structured content."""
        self._parse_header()
        if not self.header:
            return {}

        if self.header.version >= LSFVersion.V2:
            return self._parse_compressed()
        else:
            return {}

    def get_newage_blob(self) -> bytes | None:
        """Extract the NewAge binary blob from the LSF data.

        Parses the LSF structure to find the "NewAge" root node and
        returns its raw attribute data (the LSMF blob).
        """
        self._parse_header()
        if not self.header or self.header.version < LSFVersion.V2:
            return None

        self._decompress_sections()
        self._parse_string_table()
        self._parse_nodes_raw()
        self._parse_attributes_raw()

        return self._find_newage_blob()

    def _read(self, size: int) -> bytes:
        """Read bytes from current position."""
        data = self.data[self.offset:self.offset + size]
        self.offset += size
        return data

    def _parse_header(self) -> None:
        """Parse LSF header for all supported versions."""
        self.offset = 0
        magic = self._read(4)
        if magic != self.MAGIC:
            raise ValueError(f"Invalid LSF magic: {magic!r}")

        version = struct.unpack("<I", self._read(4))[0]

        # Engine version: Int32 for v1-v4, Int64 for v5+
        if version >= LSFVersion.V5:
            engine_version = struct.unpack("<q", self._read(8))[0]
        else:
            engine_version = struct.unpack("<i", self._read(4))[0]

        # Metadata: V6+ has Keys fields, V5 and earlier does not
        if version >= LSFVersion.V6:
            # MetadataV6: 48 bytes
            (strings_unc, strings_disk,
             keys_unc, keys_disk,
             nodes_unc, nodes_disk,
             attrs_unc, attrs_disk,
             values_unc, values_disk) = struct.unpack("<10I", self._read(40))
            compression_flags = struct.unpack("<B", self._read(1))[0]
            self._read(3)  # Unknown2 (1 byte) + Unknown3 (2 bytes)
            metadata_format = MetadataFormat(struct.unpack("<I", self._read(4))[0])
        elif version >= LSFVersion.V3:
            # MetadataV5: 40 bytes (no Keys fields)
            (strings_unc, strings_disk,
             nodes_unc, nodes_disk,
             attrs_unc, attrs_disk,
             values_unc, values_disk) = struct.unpack("<8I", self._read(32))
            compression_flags = struct.unpack("<B", self._read(1))[0]
            self._read(3)  # Unknown2 + Unknown3
            metadata_format = MetadataFormat(struct.unpack("<I", self._read(4))[0])
            keys_unc = 0
            keys_disk = 0
        else:
            # V1-V2: simplified header
            strings_unc = strings_disk = 0
            keys_unc = keys_disk = 0
            nodes_unc = nodes_disk = 0
            attrs_unc = attrs_disk = 0
            values_unc = values_disk = 0
            compression_flags = 0
            metadata_format = MetadataFormat.NONE

        self.header = LSFHeader(
            magic=magic,
            version=version,
            engine_version=engine_version,
            strings_uncompressed_size=strings_unc,
            strings_size_on_disk=strings_disk,
            keys_uncompressed_size=keys_unc,
            keys_size_on_disk=keys_disk,
            nodes_uncompressed_size=nodes_unc,
            nodes_size_on_disk=nodes_disk,
            attributes_uncompressed_size=attrs_unc,
            attributes_size_on_disk=attrs_disk,
            values_uncompressed_size=values_unc,
            values_size_on_disk=values_disk,
            compression_flags=compression_flags,
            metadata_format=metadata_format,
        )

    def _decompress_section(self, size_on_disk: int, uncompressed_size: int,
                            allow_chunked: bool) -> bytes:
        """Decompress a data section from the current file position."""
        if not self.header:
            return b""

        # No data
        if size_on_disk == 0 and uncompressed_size == 0:
            return b""

        # Data is not compressed (size_on_disk == 0 means stored uncompressed)
        if size_on_disk == 0 and uncompressed_size != 0:
            return self._read(uncompressed_size)

        compression_method = self.header.compression_flags & 0x0F
        is_compressed = compression_method != 0
        read_size = size_on_disk if is_compressed else uncompressed_size
        raw = self._read(read_size)

        if not is_compressed:
            return raw

        chunked = (self.header.version >= LSFVersion.V2 and allow_chunked)

        if compression_method == 2:  # LZ4
            if chunked:
                return lz4.frame.decompress(raw)
            else:
                return lz4.block.decompress(raw, uncompressed_size=uncompressed_size)
        elif compression_method == 1:  # Zlib
            import zlib
            return zlib.decompress(raw)
        elif compression_method == 3:  # Zstd
            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(raw, max_output_size=uncompressed_size)
        else:
            raise ValueError(f"Unknown compression method: {compression_method}")

    # Decompressed section buffers
    _strings_dec: bytes = b""
    _nodes_dec: bytes = b""
    _attrs_dec: bytes = b""

    def _decompress_sections(self) -> None:
        """Decompress all data sections."""
        if not self.header:
            return

        h = self.header

        # Strings: NOT chunked
        self._strings_dec = self._decompress_section(
            h.strings_size_on_disk, h.strings_uncompressed_size, allow_chunked=False)

        # Keys: NOT chunked (skip if present)
        if h.keys_size_on_disk > 0:
            self._read(h.keys_size_on_disk)
        elif h.keys_uncompressed_size > 0:
            self._read(h.keys_uncompressed_size)

        # Nodes: chunked
        self._nodes_dec = self._decompress_section(
            h.nodes_size_on_disk, h.nodes_uncompressed_size, allow_chunked=True)

        # Attributes: chunked
        self._attrs_dec = self._decompress_section(
            h.attributes_size_on_disk, h.attributes_uncompressed_size, allow_chunked=True)

        # Values: chunked
        self.values = self._decompress_section(
            h.values_size_on_disk, h.values_uncompressed_size, allow_chunked=True)

    def _parse_string_table(self) -> None:
        """Parse the hash-table format string table.

        Format: u32 numHashEntries, then per entry:
                u16 numStrings, then per string:
                u16 nameLen + nameLen bytes of UTF-8
        """
        data = self._strings_dec
        if not data:
            return

        pos = 0
        num_hash_entries = struct.unpack_from("<I", data, pos)[0]
        pos += 4

        self.names = []
        for _ in range(num_hash_entries):
            chain = []
            num_strings = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            for _ in range(num_strings):
                name_len = struct.unpack_from("<H", data, pos)[0]
                pos += 2
                name = data[pos:pos + name_len].decode("utf-8", errors="replace")
                pos += name_len
                chain.append(name)
            self.names.append(chain)

    def _resolve_name(self, name_hash_idx: int) -> str:
        """Resolve a NameHashTableIndex to a string name."""
        hash_idx = name_hash_idx >> 16
        chain_off = name_hash_idx & 0xFFFF
        try:
            return self.names[hash_idx][chain_off]
        except (IndexError, KeyError):
            return f"unknown_{hash_idx}_{chain_off}"

    def _parse_nodes_raw(self) -> None:
        """Parse node entries from decompressed node data."""
        if not self.header:
            return

        data = self._nodes_dec
        use_v3 = (self.header.version >= LSFVersion.V3
                  and self.header.metadata_format == MetadataFormat.KEYS_AND_ADJACENCY)

        node_size = 16 if use_v3 else 12
        node_count = len(data) // node_size

        self.nodes = []
        for i in range(node_count):
            off = i * node_size
            name_hash_idx = struct.unpack_from("<I", data, off)[0]

            if use_v3:
                # V3: NameHashTableIndex(4) + ParentIndex(4) + NextSiblingIndex(4) + FirstAttributeIndex(4)
                parent_idx = struct.unpack_from("<i", data, off + 4)[0]
                first_attr = struct.unpack_from("<i", data, off + 12)[0]
            else:
                # V2: NameHashTableIndex(4) + FirstAttributeIndex(4) + ParentIndex(4)
                first_attr = struct.unpack_from("<i", data, off + 4)[0]
                parent_idx = struct.unpack_from("<i", data, off + 8)[0]

            self.nodes.append({
                "name": self._resolve_name(name_hash_idx),
                "first_attribute": first_attr,
                "parent": parent_idx,
                "attributes": {},
                "children": [],
            })

    def _parse_attributes_raw(self) -> None:
        """Parse attribute entries from decompressed attribute data."""
        if not self.header:
            return

        data = self._attrs_dec
        use_v3 = (self.header.version >= LSFVersion.V3
                  and self.header.metadata_format == MetadataFormat.KEYS_AND_ADJACENCY)

        self.attributes = []

        if use_v3:
            # V3 attributes: 16 bytes each
            # NameHashTableIndex(4) + TypeAndLength(4) + NextAttributeIndex(4) + Offset(4)
            attr_count = len(data) // 16
            for i in range(attr_count):
                off = i * 16
                name_hash_idx = struct.unpack_from("<I", data, off)[0]
                type_and_length = struct.unpack_from("<I", data, off + 4)[0]
                next_attr = struct.unpack_from("<i", data, off + 8)[0]
                value_offset = struct.unpack_from("<I", data, off + 12)[0]

                self.attributes.append({
                    "name": self._resolve_name(name_hash_idx),
                    "type": type_and_length & 0x3F,
                    "length": type_and_length >> 6,
                    "value_offset": value_offset,
                    "next": next_attr,
                })
        else:
            # V2 attributes: 12 bytes each
            # NameHashTableIndex(4) + TypeAndLength(4) + NodeIndex(4)
            # DataOffset is computed sequentially; NextAttributeIndex is computed from NodeIndex
            attr_count = len(data) // 12
            data_offset = 0
            prev_attr_refs: dict[int, int] = {}

            for i in range(attr_count):
                off = i * 12
                name_hash_idx = struct.unpack_from("<I", data, off)[0]
                type_and_length = struct.unpack_from("<I", data, off + 4)[0]
                node_idx = struct.unpack_from("<i", data, off + 8)[0]

                type_id = type_and_length & 0x3F
                length = type_and_length >> 6

                attr = {
                    "name": self._resolve_name(name_hash_idx),
                    "type": type_id,
                    "length": length,
                    "value_offset": data_offset,
                    "next": -1,
                    "_node_idx": node_idx,
                }

                # Link attributes within same node (node_idx + 1 per LSLib convention)
                actual_node = node_idx + 1
                if actual_node in prev_attr_refs:
                    self.attributes[prev_attr_refs[actual_node]]["next"] = i
                prev_attr_refs[actual_node] = i

                data_offset += length
                self.attributes.append(attr)

    def _find_newage_blob(self) -> bytes | None:
        """Find the NewAge node's raw binary blob attribute."""
        # Find root node named "NewAge"
        newage_idx = None
        for i, node in enumerate(self.nodes):
            if node["parent"] == -1 and node["name"] == "NewAge":
                newage_idx = i
                break

        if newage_idx is None:
            return None

        # Walk the NewAge node's attributes to find the large blob
        node = self.nodes[newage_idx]
        attr_idx = node["first_attribute"]

        while attr_idx != -1 and attr_idx < len(self.attributes):
            attr = self.attributes[attr_idx]
            # The LSMF blob is the largest attribute (>100KB)
            if attr["length"] > 100000:
                off = attr["value_offset"]
                length = attr["length"]
                blob = self.values[off:off + length]
                if blob[:4] == b"LSMF":
                    return blob
            attr_idx = attr["next"]

        # Fallback: scan values for LSMF magic
        idx = self.values.find(b"LSMF")
        if idx >= 0:
            # Try to determine length from context
            # Read enough data to parse LSMF header
            return self.values[idx:]

        return None

    def _parse_compressed(self) -> dict[str, Any]:
        """Parse LSF with compression (v2+)."""
        self._decompress_sections()
        self._parse_string_table()
        self._parse_nodes_raw()
        self._parse_attributes_raw()
        return self._build_tree()

    def _read_attribute_value(self, attr: dict) -> Any:
        """Read attribute value from values buffer."""
        offset = attr["value_offset"]
        attr_type = attr["type"]
        length = attr.get("length", 0)

        try:
            if attr_type == NodeAttribute.BOOL:
                return bool(self.values[offset])
            elif attr_type == NodeAttribute.BYTE:
                return self.values[offset]
            elif attr_type == NodeAttribute.INT8:
                return struct.unpack_from("<b", self.values, offset)[0]
            elif attr_type == NodeAttribute.SHORT:
                return struct.unpack_from("<h", self.values, offset)[0]
            elif attr_type == NodeAttribute.USHORT:
                return struct.unpack_from("<H", self.values, offset)[0]
            elif attr_type == NodeAttribute.INT:
                return struct.unpack_from("<i", self.values, offset)[0]
            elif attr_type == NodeAttribute.UINT:
                return struct.unpack_from("<I", self.values, offset)[0]
            elif attr_type in (NodeAttribute.INT64, NodeAttribute.LONG):
                return struct.unpack_from("<q", self.values, offset)[0]
            elif attr_type == NodeAttribute.UINT64:
                return struct.unpack_from("<Q", self.values, offset)[0]
            elif attr_type == NodeAttribute.FLOAT:
                return struct.unpack_from("<f", self.values, offset)[0]
            elif attr_type == NodeAttribute.DOUBLE:
                return struct.unpack_from("<d", self.values, offset)[0]
            elif attr_type in (NodeAttribute.STRING, NodeAttribute.PATH,
                               NodeAttribute.FIXEDSTRING, NodeAttribute.LSSTRING):
                slen = struct.unpack_from("<I", self.values, offset)[0]
                return self.values[offset + 4:offset + 4 + slen].decode(
                    "utf-8", errors="replace").rstrip("\x00")
            elif attr_type == NodeAttribute.UUID:
                uuid_bytes = self.values[offset:offset + 16]
                a = struct.unpack_from("<I", uuid_bytes, 0)[0]
                b = struct.unpack_from("<H", uuid_bytes, 4)[0]
                c = struct.unpack_from("<H", uuid_bytes, 6)[0]
                return f"{a:08x}-{b:04x}-{c:04x}-{uuid_bytes[8:10].hex()}-{uuid_bytes[10:16].hex()}"
            elif attr_type == NodeAttribute.VEC3:
                return list(struct.unpack_from("<fff", self.values, offset))
            elif attr_type == NodeAttribute.VEC4:
                return list(struct.unpack_from("<ffff", self.values, offset))
            elif attr_type == NodeAttribute.TRANSLATEDSTRING:
                version = struct.unpack_from("<H", self.values, offset)[0]
                slen = struct.unpack_from("<I", self.values, offset + 2)[0]
                return self.values[offset + 6:offset + 6 + slen].decode(
                    "utf-8", errors="replace").rstrip("\x00")
            elif attr_type == NodeAttribute.SCRATCHBUFFER:
                # Raw binary data - return length info
                if length > 10000:
                    magic = self.values[offset:offset + 4]
                    return f"<buffer_{length}_bytes_magic={magic!r}>"
                return self.values[offset:offset + length]
            else:
                return f"<raw_type_{attr_type}>"
        except Exception:
            return None

    def _build_tree(self) -> dict[str, Any]:
        """Build the node tree structure."""
        # Link attributes to nodes
        for i, node in enumerate(self.nodes):
            attr_idx = node["first_attribute"]
            while attr_idx != -1 and attr_idx < len(self.attributes):
                attr = self.attributes[attr_idx]
                value = self._read_attribute_value(attr)
                node["attributes"][attr["name"]] = value
                attr_idx = attr["next"]

        # Build parent-child relationships
        for i, node in enumerate(self.nodes):
            parent_idx = node["parent"]
            if 0 <= parent_idx < len(self.nodes):
                self.nodes[parent_idx]["children"].append(i)

        # Find root nodes and build result
        result = {}
        for i, node in enumerate(self.nodes):
            if node["parent"] == -1:
                result[node["name"]] = self._node_to_dict(i)

        return result

    def _node_to_dict(self, node_idx: int) -> dict[str, Any]:
        """Convert a node and its children to a dictionary."""
        node = self.nodes[node_idx]
        result = dict(node["attributes"])

        # Group children by name
        children_by_name: dict[str, list] = {}
        for child_idx in node["children"]:
            child = self.nodes[child_idx]
            child_name = child["name"]
            if child_name not in children_by_name:
                children_by_name[child_name] = []
            children_by_name[child_name].append(self._node_to_dict(child_idx))

        for name, children in children_by_name.items():
            if len(children) == 1:
                result[name] = children[0]
            else:
                result[name] = children

        return result


def parse_lsx(data: bytes) -> dict[str, Any]:
    """Parse LSX (XML) format as fallback."""
    try:
        root = ET.fromstring(data)
        return _element_to_dict(root)
    except ET.ParseError:
        return {}


def _element_to_dict(element: ET.Element) -> dict[str, Any]:
    """Convert XML element to dictionary."""
    result: dict[str, Any] = dict(element.attrib)

    children_by_tag: dict[str, list] = {}
    for child in element:
        tag = child.tag
        if tag not in children_by_tag:
            children_by_tag[tag] = []
        children_by_tag[tag].append(_element_to_dict(child))

    for tag, children in children_by_tag.items():
        if len(children) == 1:
            result[tag] = children[0]
        else:
            result[tag] = children

    if element.text and element.text.strip():
        result["_text"] = element.text.strip()

    return result
