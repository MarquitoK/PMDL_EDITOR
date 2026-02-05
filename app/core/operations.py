import struct
from typing import List
from .parts_index import PartIndexEntry
from .header import PmdlHeader
from .converters import opacity_u16_from_percent
from .flags import FLAG_MAP_LABEL_TO_VALUE


def export_part(blob: bytearray, part: PartIndexEntry) -> bytes:
    """
    Extrae los bytes de una parte específica.
    
    Args:
        blob: Datos del archivo PMDL.
        part: Entrada de la parte a exportar.
        
    Returns:
        Bytes de la parte.
        
    Raises:
        ValueError: Si el rango es inválido.
    """
    off = part.part_offset
    ln = part.part_length
    
    if off < 0 or ln <= 0 or off + ln > len(blob):
        raise ValueError(f"Rango inválido al exportar (offset={off}, longitud={ln}).")
    
    return bytes(blob[off:off + ln])


def delete_part(blob: bytearray, hdr: PmdlHeader, parts: List[PartIndexEntry], part_index: int):
    """
    Elimina una parte del PMDL y ajusta el índice.
    
    Args:
        blob: Datos del archivo PMDL (modificado in-place).
        hdr: Header del PMDL (modificado in-place).
        parts: Lista de partes (modificada in-place).
        part_index: Índice de la parte a eliminar.
        
    Raises:
        ValueError: Si el índice es inválido.
    """
    if not (0 <= part_index < len(parts)):
        raise ValueError("Índice de parte inválido.")
    
    index_base = hdr.parts_index_offset
    stride = 0x20
    old_count = hdr.part_count
    
    # Parte a borrar
    p = parts[part_index]
    off = p.part_offset
    ln = p.part_length
    
    # (a) Eliminar bytes de la PARTE en el blob
    del blob[off:off + ln]
    
    # (b) Restar longitud a offsets de partes que estaban debajo
    for j in range(part_index + 1, len(parts)):
        parts[j].part_offset -= ln
    
    # (c.1) Eliminar bloque de índice (0x20)
    entry_off = index_base + part_index * stride
    del blob[entry_off:entry_off + stride]
    
    # (c.2) Restar 0x20 a offsets de inicio de parte
    for j in range(len(parts)):
        if j == part_index:
            continue
        parts[j].part_offset -= stride
    
    # (c.3) Quitar entrada en memoria
    parts.pop(part_index)
    
    # (d) Decrementar contador de partes
    new_count = old_count - 1
    struct.pack_into("<I", blob, 0x5C, new_count)
    hdr.part_count = new_count
    
    # (e) Truncar residuos
    if hdr.part_count > 0:
        last = parts[-1]
        end_of_model = last.part_offset + last.part_length
    else:
        end_of_model = index_base
    
    if len(blob) > end_of_model:
        del blob[end_of_model:]


def import_part(blob: bytearray, hdr: PmdlHeader, parts: List[PartIndexEntry], new_part_data: bytes):
    """
    Importa una nueva parte al PMDL.
    
    Args:
        blob: Datos del archivo PMDL (modificado in-place).
        hdr: Header del PMDL (modificado in-place).
        parts: Lista de partes (modificada in-place).
        new_part_data: Bytes de la nueva parte.
        
    Returns:
        Tupla (offset, length) de la parte importada.
        
    Raises:
        ValueError: Si la parte está vacía.
    """
    if not new_part_data:
        raise ValueError("La parte está vacía.")
    
    # 1) Insertar bloque de índice al final
    old_count = hdr.part_count
    index_base = hdr.parts_index_offset
    index_end_before = index_base + old_count * 0x20
    blob[index_end_before:index_end_before] = b"\x00" * 0x20
    
    # 2) Actualizar contador
    new_count = old_count + 1
    struct.pack_into("<I", blob, 0x5C, new_count)
    hdr.part_count = new_count
    
    # 3) Sumar 0x20 a todos los offsets existentes
    stride = 0x20
    for p in parts:
        p.part_offset += stride
    
    # 4) Punto de inserción
    if old_count > 0:
        last = parts[-1]
        insert_pos = last.part_offset + last.part_length
    else:
        insert_pos = index_base + new_count * stride
    
    # 5) Insertar bytes de la parte
    blob[insert_pos:insert_pos] = new_part_data
    
    # 6) Preparar nuevo índice
    if old_count > 0:
        last_id_low = parts[-1].part_id & 0xFF
        new_id_low = min(0xFF, last_id_low + 1)
        new_part_id = (parts[-1].part_id & 0xFF00) | new_id_low
    else:
        new_part_id = 0x0000
    
    new_opacity = 0xFFFF
    new_flag = 0x00000000
    new_offset = insert_pos
    new_length = len(new_part_data)
    
    # 7) Escribir bloque de índice
    new_entry_off = index_base + old_count * stride
    struct.pack_into("<H", blob, new_entry_off + 0x00, new_part_id & 0xFFFF)
    struct.pack_into("<H", blob, new_entry_off + 0x02, new_opacity & 0xFFFF)
    struct.pack_into("<I", blob, new_entry_off + 0x04, new_offset & 0xFFFFFFFF)
    struct.pack_into("<I", blob, new_entry_off + 0x08, new_length & 0xFFFFFFFF)
    struct.pack_into("<I", blob, new_entry_off + 0x0C, new_flag & 0xFFFFFFFF)
    
    # 8) Actualizar modelo en memoria
    parts.append(PartIndexEntry(
        part_id=new_part_id,
        opacity=new_opacity,
        part_offset=new_offset,
        part_length=new_length,
        special_flag=new_flag
    ))
    
    # 9) Truncar residuos
    end_of_model = new_offset + new_length
    if len(blob) > end_of_model:
        del blob[end_of_model:]
    
    return new_offset, new_length

def replace_part(blob: bytearray, hdr: PmdlHeader, parts: List[PartIndexEntry], part_data: bytearray, id_part: int):
    """
    remplaza una parte existen
    :param blob: Datos del archivo PMDL.
    :param hdr: Header del PMDL.
    :param parts: Lista de partes.
    :param part_data: Bytes de la nueva parte.
    :param id_part: Identificador de la parte del PMDL.
    """

    offset_part = parts[id_part].part_offset
    old_length = parts[id_part].part_length
    offset_part_end = offset_part + old_length

    # 1️⃣ Reemplazar datos de la parte EN SITIO
    blob[offset_part:offset_part_end] = part_data

    # 2️⃣ Actualizar longitud
    new_length = len(part_data)
    parts[id_part].part_length = new_length

    # 3️⃣ Calcular diferencia de tamaño
    delta = new_length - old_length

    # 4️⃣ Ajustar offsets de las partes siguientes
    if delta != 0:
        for i in range(id_part + 1, len(parts)):
            parts[i].part_offset += delta

    # 5️⃣ Reescribir tabla de índices
    base_index = hdr.parts_index_offset

    for i, p in enumerate(parts):
        entry_off = base_index + i * 0x20

        struct.pack_into("<I", blob, entry_off + 4,  p.part_offset)
        struct.pack_into("<I", blob, entry_off + 8,  p.part_length)

    return parts



def add_part_from_secondary(blob_dest: bytearray, hdr_dest: PmdlHeader, parts_dest: List[PartIndexEntry],
                            blob_src: bytearray, part_src: PartIndexEntry):
    """
    Agrega una parte desde un PMDL secundario al principal.
    
    Args:
        blob_dest: Blob del PMDL destino (modificado in-place).
        hdr_dest: Header del PMDL destino (modificado in-place).
        parts_dest: Lista de partes del destino (modificada in-place).
        blob_src: Blob del PMDL origen.
        part_src: Entrada de la parte a copiar.
        
    Returns:
        Tupla (offset, length) de la parte agregada.
        
    Raises:
        ValueError: Si el rango es inválido.
    """
    src_off = part_src.part_offset
    src_len = part_src.part_length
    
    if src_off < 0 or src_len <= 0 or src_off + src_len > len(blob_src):
        raise ValueError("Rango inválido en la parte del PMDL secundario.")
    
    src_bytes = bytes(blob_src[src_off:src_off + src_len])
    src_id = part_src.part_id & 0xFFFF
    src_opac = part_src.opacity & 0xFFFF
    src_flag = part_src.special_flag & 0xFFFFFFFF
    
    # Insertar bloque de índice
    index_base = hdr_dest.parts_index_offset
    stride = 0x20
    old_count = hdr_dest.part_count
    index_end_before = index_base + old_count * stride
    
    blob_dest[index_end_before:index_end_before] = b"\x00" * stride
    
    # Actualizar contador
    new_count = old_count + 1
    struct.pack_into("<I", blob_dest, 0x5C, new_count)
    hdr_dest.part_count = new_count
    
    # Sumar +0x20 a todos los offsets
    for p in parts_dest:
        p.part_offset += stride
    
    # Punto de inserción
    if old_count > 0:
        last = parts_dest[-1]
        insert_pos = last.part_offset + last.part_length
    else:
        insert_pos = index_base + new_count * stride
    
    # Insertar bytes
    blob_dest[insert_pos:insert_pos] = src_bytes
    
    # Escribir índice
    new_entry_off = index_base + old_count * stride
    struct.pack_into("<H", blob_dest, new_entry_off + 0x00, src_id)
    struct.pack_into("<H", blob_dest, new_entry_off + 0x02, src_opac)
    struct.pack_into("<I", blob_dest, new_entry_off + 0x04, insert_pos)
    struct.pack_into("<I", blob_dest, new_entry_off + 0x08, src_len)
    struct.pack_into("<I", blob_dest, new_entry_off + 0x0C, src_flag)
    
    # Actualizar modelo
    parts_dest.append(PartIndexEntry(
        part_id=src_id,
        opacity=src_opac,
        part_offset=insert_pos,
        part_length=src_len,
        special_flag=src_flag
    ))
    
    # Truncar residuos
    end_of_model = insert_pos + src_len
    if len(blob_dest) > end_of_model:
        del blob_dest[end_of_model:]
    
    return insert_pos, src_len


def sync_parts_from_ui(blob: bytearray, hdr: PmdlHeader, parts: List[PartIndexEntry], 
                       ui_data: List[dict]):
    """
    Sincroniza las partes en memoria con los datos de la UI.
    
    Args:
        blob: Datos del archivo PMDL (modificado in-place).
        hdr: Header del PMDL.
        parts: Lista de partes (modificada in-place).
        ui_data: Lista de diccionarios con 'depth', 'opacity_pct', 'flag_label'.
    """
    for i, data in enumerate(ui_data):
        if i >= len(parts):
            break
        
        # Capa/ID
        low = data.get('depth', 0) & 0xFF
        current = parts[i].part_id
        parts[i].part_id = (current & 0xFF00) | low
        
        # Opacidad
        pct = max(0, min(100, data.get('opacity_pct', 100)))
        parts[i].opacity = opacity_u16_from_percent(pct)
        
        # Función
        label = data.get('flag_label', 'Ninguna')
        value = FLAG_MAP_LABEL_TO_VALUE.get(label, 0x00)
        parts[i].special_flag = value
    
    # Escribir en blob
    base = hdr.parts_index_offset
    stride = 0x20
    for i, p in enumerate(parts):
        off = base + i * stride
        struct.pack_into("<H", blob, off + 0x00, p.part_id & 0xFFFF)
        struct.pack_into("<H", blob, off + 0x02, p.opacity & 0xFFFF)
        struct.pack_into("<I", blob, off + 0x04, p.part_offset & 0xFFFFFFFF)
        struct.pack_into("<I", blob, off + 0x08, p.part_length & 0xFFFFFFFF)
        struct.pack_into("<I", blob, off + 0x0C, p.special_flag & 0xFFFFFFFF)