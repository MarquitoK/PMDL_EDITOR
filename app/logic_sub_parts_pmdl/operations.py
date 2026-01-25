from app.core import PartIndexEntry, export_part
from app.logic_sub_parts_pmdl.sub_parts_index import SubPartIndexEntry


def export_sub_part(blob: bytearray, part: PartIndexEntry, subpart: SubPartIndexEntry) -> bytes:
    data_part = export_part(blob, part)

    offset = subpart.sub_part_offset
    size = calc_subpart_size(subpart.num_vertices, subpart.num_bones)

    return bytes(data_part[offset: offset + size])

def calc_subpart_size(num_vertices: int, num_bones: int, vertex = False) -> int:
    """
    Calcula el tamaño total (en bytes) de una subparte.

    :param num_vertices: cantidad de vértices
    :param num_bones: cantidad de huesos por vértice
    :return: tamaño total en bytes
    """
    if num_vertices < 0 or num_bones < 0:
        raise ValueError("la cantidad de vertices o bones no puede ser negativa")

    bytes_per_vertex = (2 * num_bones) + 8
    if vertex:
        return bytes_per_vertex

    total_size = bytes_per_vertex * num_vertices

    return total_size
