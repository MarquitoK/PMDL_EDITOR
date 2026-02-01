import struct

from app.logic_sub_parts_pmdl.sub_parts_index import SubPartIndexEntry


def export_sub_part(blob: bytearray, part: int, subpart: SubPartIndexEntry) -> bytes:
    """
    Exporta una subparte
    :param blob: blob de la part
    :param part: parte donde esta ubicada la subpart
    :param subpart: info de la subpart

    """
    data_part = blob.get(f"{part}", None)

    if data_part is None:
        raise ValueError("la parte no existe en memoria")

    offset = subpart.sub_part_offset
    size = calc_subpart_size(subpart.num_vertices, subpart.num_bones)

    return bytes(data_part[offset: offset + size])

def import_sub_part(blob: bytearray, part: int, subpart: SubPartIndexEntry, data_subpart: bytearray):
    """
    Reemplaza una subpart existente en memoria
    :param blob: blob de la part
    :param part: parte donde esta ubicada la subpart
    :param subpart: info de la subpart
    :param data_subpart: data de la subpart a importar
    :return: tupla (parte actualizad, size)
    """
    data_part = blob.get(f"{part}", None)

    if data_part is None:
        raise ValueError("la parte no existe en memoria")

    offset = subpart.sub_part_offset
    size = calc_subpart_size(subpart.num_vertices, subpart.num_bones)

    # reemplazar la subpart
    data_part = data_part[:offset] + data_subpart + data_part[offset + size:]
    data_part = bytearray(data_part)

    # tamaño de la subpart importada
    size_new = len(data_subpart)
    cant = (offset+size_new) - (offset+size)
    num_parts, = struct.unpack_from("<I", data_part, 0)

    # actualizar offsets de las subparts en la parte
    for i in range(subpart.sub_part + 2, num_parts + 1):
        offset_subpart, = struct.unpack_from("<I", data_part, 0x10 * i)
        offset_subpart+=cant
        struct.pack_into("<I", data_part, 0x10 * i, offset_subpart)

    # reemplazar la parte en memoria
    # blob[part] = data_part

    return data_part, cant

def calc_subpart_size(num_vertices: int, num_bones: int, vertex = False) -> int:
    """
    Calcula el tamaño total (en bytes) de una subparte.

    :param num_vertices: cantidad de vértices
    :param num_bones: cantidad de huesos por vértice
    :param vertex: si es True devuelve el tamaño de un vertex en bytes
    :return: tamaño total en bytes
    """
    if num_vertices < 0 or num_bones < 0:
        raise ValueError("la cantidad de vertices o bones no puede ser negativa")

    bytes_per_vertex = (2 * num_bones) + 8
    if vertex:
        return bytes_per_vertex

    total_size = bytes_per_vertex * num_vertices

    return total_size

def align_16(buf: bytearray):
    padding = (-len(buf)) % 0x10
    if padding:
        buf.extend(b'\x00' * padding)
