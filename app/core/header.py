import struct
from dataclasses import dataclass


@dataclass
class PmdlHeader:
    magic: bytes
    bone_count: int
    bones_offset: int
    part_count: int
    parts_index_offset: int


def parse_header(blob: bytes) -> PmdlHeader:
    if len(blob) < 0x70:
        raise ValueError("Archivo demasiado corto para cabecera .pmdl (0x70 bytes).")
    
    magic = blob[0x00:0x04]
    if magic != b"pMdl":
        raise ValueError(f"Firma inválida: {magic} (se esperaba b'pMdl').")
    
    bone_count = blob[0x08]
    bones_offset = struct.unpack_from("<I", blob, 0x50)[0]
    part_count = struct.unpack_from("<I", blob, 0x5C)[0]
    parts_index_offset = struct.unpack_from("<I", blob, 0x60)[0]
    
    return PmdlHeader(magic, bone_count, bones_offset, part_count, parts_index_offset)