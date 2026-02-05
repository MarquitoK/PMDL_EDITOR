import struct

from app.logic_sub_parts_pmdl.sub_parts_index import SubPartIndexEntry


def export_sub_part(blob: dict, part: int, subpart: SubPartIndexEntry) -> bytes:
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

def import_sub_part(blob: dict, part: int, subpart: SubPartIndexEntry, data_subpart: bytearray):
    """
    Reemplaza una subpart existente en memoria
    :param blob: blob de la part
    :param part: parte donde esta ubicada la subpart
    :param subpart: info de la subpart
    :param data_subpart: data de la subpart a importar
    :return: tupla (parte actualizad, size)
    """
    data_part = blob.get(f"{part}", None)

    if not data_part:
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

def insert_sub_part(blob: dict, part: int, subpart: SubPartIndexEntry, data_subpart: bytearray, inf_subpart: bytearray) -> tuple[bytearray, int, int]:
    """
    inserta una subparte en la memoria
    :param blob: blob de la part
    :param part: parte donde esta ubicada la subpart
    :param subpart: info de la subpart donde se insertara
    :param data_subpart: data de la subpart a importar (vertices)
    :param inf_subpart: info de la subpart a importar

    :return: tupla (parte actualizad, cant a sumar, offset de la parte insertada)
    """
    data_part = blob.get(f"{part}", None)
    # print(len(data_part))

    if not data_part:
        raise ValueError("la parte no existe en memoria")

    data_part = bytearray(data_part)

    # offset de la subparte
    offset = subpart.sub_part_offset
    size = calc_subpart_size(subpart.num_vertices, subpart.num_bones)
    num_subpart = subpart.sub_part + 1

    num_parts, = struct.unpack_from("<I", data_part, 0)

    # sumar el 0x10 incialmente a los offsets de las subpartes
    for i in range(1, num_parts + 1):
        offset_old, = struct.unpack_from("<I", data_part, 0x10 * i)
        offset_old+=0x10
        struct.pack_into("<I", data_part, 0x10 * i, offset_old)

    # escribir offset donde empiece la subparte
    offser_insert = offset + size + 0x10
    struct.pack_into("<I", inf_subpart, 0xc, offser_insert)
    # insertar la informacion
    pos = 4 + (0x10 * num_subpart)
    data_part[pos:pos] = inf_subpart

    num_parts+=1
    struct.pack_into("<I", data_part, 0, num_parts)

    # insertar los vertices de la subparte
    size_new = len(data_subpart)
    # data_part.insert(offser_insert, data_subpart)
    data_part[offser_insert:offser_insert] = data_subpart

    # arreglar offsets de las subpartes
    for i in range(num_subpart + 2, num_parts + 1):
        offset_old, = struct.unpack_from("<I", data_part, 0x10 * i)
        offset_old+=size_new
        struct.pack_into("<I", data_part, 0x10 * i, offset_old)

    # cantidad a sumar
    res_cant = size_new
    return data_part, res_cant, offser_insert - 0x10

def delete_sub_part(blob: dict, part:int, subpart: SubPartIndexEntry) -> tuple[bytearray, int]:
    """
    Elimina una subparte de la memoria
    :param blob: blob de la part
    :param part: parte donde se eliminara
    :param subpart: info de la subpart que se eliminara

    :return: data_part, tamaño de la subparte eliminada
    """
    data_part = blob.get(f"{part}", None)
    # print(len(data_part))

    if not data_part:
        raise ValueError("la parte no existe en memoria")

    data_part = bytearray(data_part)

    offset = subpart.sub_part_offset
    size = calc_subpart_size(subpart.num_vertices, subpart.num_bones)

    # borrar subparte y datos de la misma
    del data_part[offset: offset + size]
    offset_inf_subpart = (subpart.sub_part * 0x10) + 4
    del data_part[offset_inf_subpart: offset_inf_subpart + 0x10]

    num_subparts, = struct.unpack_from("<I", data_part, 0)
    # arreglar offsets
    for i in range(1, num_subparts):
        offset_old, = struct.unpack_from("<I", data_part, 0x10 * i)
        offset_old -= 0x10
        struct.pack_into("<I", data_part, 0x10 * i, offset_old)

    for i in range(subpart.sub_part + 1, num_subparts):
        offset_old, = struct.unpack_from("<I", data_part, 0x10 * i)
        offset_old -= size
        struct.pack_into("<I", data_part, 0x10 * i, offset_old)

    return data_part, size

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
