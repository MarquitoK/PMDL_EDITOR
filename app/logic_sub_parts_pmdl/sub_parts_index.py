import struct
from dataclasses import dataclass
from typing import List


@dataclass
class SubPartIndexEntry:
    """Entrada del índice de subpartes."""
    sub_part: int
    sub_part_offset: int
    num_vertices: int
    num_bones: int
    id_bones: list[int]
    unk: int

def parse_subparts_index(blob_subpart: bytes) -> List[SubPartIndexEntry]:
    entries: List[SubPartIndexEntry] = []
    offset = 4
    chunk_size = 0x10
    num_subparts, = struct.unpack_from("<I", blob_subpart, 0)

    for i in range(num_subparts):
        chunk = blob_subpart[offset:offset + chunk_size]

        if len(chunk) < chunk_size:
            raise ValueError(f"Índice de subpartes incompleto en entrada {i}, offset {offset}.")

        offset += chunk_size

        sub_part = i
        num_vertices, = struct.unpack_from("<B", chunk, 0)
        num_bones, = struct.unpack_from("<B", chunk, 2)
        id_bones:list[int] = []

        for bone in range(4,8):
            id_bone, = struct.unpack_from("<B", chunk, bone)
            id_bones.append(id_bone)
        unk, = struct.unpack_from("<I", chunk, 8)
        sub_part_offset, = struct.unpack_from("<I", chunk, 0xc)

        entries.append(SubPartIndexEntry(sub_part, sub_part_offset, num_vertices, num_bones, id_bones, unk))
    return entries