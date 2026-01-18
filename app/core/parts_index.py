import struct
from dataclasses import dataclass
from typing import List
from .header import PmdlHeader


@dataclass
class PartIndexEntry:
    """Entrada del índice de partes."""
    part_id: int
    opacity: int
    part_offset: int
    part_length: int
    special_flag: int


def parse_parts_index(blob: bytes, hdr: PmdlHeader) -> List[PartIndexEntry]:
    entries: List[PartIndexEntry] = []
    base = hdr.parts_index_offset
    size = 0x20
    
    for i in range(hdr.part_count):
        off = base + i * size
        chunk = blob[off:off + size]
        
        if len(chunk) < size:
            raise ValueError(f"Índice de partes incompleto en entrada {i}.")
        
        part_id, = struct.unpack_from("<H", chunk, 0x00)
        opacity, = struct.unpack_from("<H", chunk, 0x02)
        part_offset, = struct.unpack_from("<I", chunk, 0x04)
        part_length, = struct.unpack_from("<I", chunk, 0x08)
        special_flag, = struct.unpack_from("<I", chunk, 0x0C)
        
        entries.append(PartIndexEntry(part_id, opacity, part_offset, part_length, special_flag))
    
    return entries