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

    # id_bones_old:list[int] = []

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

        # verificar las id 0xFF
        # id_bones = _reemplazar_ff(id_bones, id_bones_old)
        # id_bones_old = id_bones
        entries.append(SubPartIndexEntry(sub_part, sub_part_offset, num_vertices, num_bones, id_bones, unk))
    return entries

def _reemplazar_ff(lista_actual:list[int], lista_anterior:list[int]) -> List[int]:
    """
    reemplaza los 0xff de las id de los bones
    """
    if not lista_anterior:
        return lista_actual

    return [
        lista_anterior[i] if v == 0xff else v
        for i, v in enumerate(lista_actual)
    ]