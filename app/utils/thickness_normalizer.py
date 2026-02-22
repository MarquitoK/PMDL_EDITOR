import struct
from typing import Tuple


GROSOR_MAXIMO = 512.0


def leer_grosor(blob: bytes) -> Tuple[float, float, float]:
    """
    Lee los valores de grosor (bounding box) del header del PMDL.
    
    Args:
        blob: Datos del archivo PMDL.
        
    Returns:
        Tupla (grosor_x, grosor_y, grosor_z) como floats.
    """
    if len(blob) < 0x4C:
        raise ValueError("Archivo PMDL demasiado corto para leer grosor.")
    
    gx = struct.unpack_from("<f", blob, 0x40)[0]
    gy = struct.unpack_from("<f", blob, 0x44)[0]
    gz = struct.unpack_from("<f", blob, 0x48)[0]
    
    return gx, gy, gz


def escribir_grosor_maximo(blob: bytearray):
    """
    Escribe grosor máximo (512.0) en los tres ejes del header.
    
    Args:
        blob: Datos del archivo PMDL (modificado in-place).
    """
    if len(blob) < 0x4C:
        raise ValueError("Archivo PMDL demasiado corto para escribir grosor.")
    
    struct.pack_into("<f", blob, 0x40, GROSOR_MAXIMO)
    struct.pack_into("<f", blob, 0x44, GROSOR_MAXIMO)
    struct.pack_into("<f", blob, 0x48, GROSOR_MAXIMO)


def convertir_vertices_parte_a_grosor_maximo(blob: bytearray, part_offset: int, 
                                              grosor_original: Tuple[float, float, float]):
    """
    Convierte los vértices de UNA parte a grosor máximo.
    
    Args:
        blob: Datos del PMDL (modificado in-place).
        part_offset: Offset donde comienza la parte.
        grosor_original: Tupla (gx, gy, gz) del grosor original.
    """
    gx, gy, gz = grosor_original
    
    # Calcular factores de escala
    factor_x = gx / GROSOR_MAXIMO if gx > 0 else 1.0
    factor_y = gy / GROSOR_MAXIMO if gy > 0 else 1.0
    factor_z = gz / GROSOR_MAXIMO if gz > 0 else 1.0
    
    # Si ya está en grosor máximo, no hacer nada
    if factor_x == 1.0 and factor_y == 1.0 and factor_z == 1.0:
        return
    
    # Leer cantidad de subpartes
    cantidad_subpartes = struct.unpack_from("<I", blob, part_offset)[0]
    
    # Procesar cada subparte
    for sub_idx in range(cantidad_subpartes):
        entrada = part_offset + 0x04 + (sub_idx * 0x10)
        
        num_vertices = struct.unpack_from("<H", blob, entrada)[0]
        num_huesos   = struct.unpack_from("<H", blob, entrada + 0x02)[0]
        offset_sub   = struct.unpack_from("<I", blob, entrada + 0x0C)[0]
        
        tamaño_pesos   = num_huesos * 2
        tamaño_vertice = tamaño_pesos + 2 + 6  # pesos + UVs(2) + coords(6)
        
        # Convertir cada vértice
        for v in range(num_vertices):
            pos_coords = part_offset + offset_sub + (v * tamaño_vertice) + tamaño_pesos + 2
            
            # Leer coordenadas actuales (int16)
            cx = struct.unpack_from("<h", blob, pos_coords)[0]
            cy = struct.unpack_from("<h", blob, pos_coords + 2)[0]
            cz = struct.unpack_from("<h", blob, pos_coords + 4)[0]
            
            # Aplicar factor de escala
            cx = max(-32768, min(32767, int(round(cx * factor_x))))
            cy = max(-32768, min(32767, int(round(cy * factor_y))))
            cz = max(-32768, min(32767, int(round(cz * factor_z))))
            
            # Escribir coordenadas convertidas
            struct.pack_into("<h", blob, pos_coords,     cx)
            struct.pack_into("<h", blob, pos_coords + 2, cy)
            struct.pack_into("<h", blob, pos_coords + 4, cz)


def normalizar_pmdl_completo(blob: bytearray, parts_index_offset: int, 
                              parts_list: list) -> bool:
    """
    Normaliza TODAS las partes de un PMDL a grosor máximo.
    
    Args:
        blob: Datos del PMDL (modificado in-place).
        parts_index_offset: Offset del índice de partes.
        parts_list: Lista de PartIndexEntry del PMDL.
        
    Returns:
        True si se realizó la normalización, False si ya estaba normalizado.
    """
    # Leer grosor actual
    grosor_actual = leer_grosor(blob)
    gx, gy, gz = grosor_actual
    
    # Verificar si ya está en grosor máximo
    if abs(gx - GROSOR_MAXIMO) < 0.01 and \
       abs(gy - GROSOR_MAXIMO) < 0.01 and \
       abs(gz - GROSOR_MAXIMO) < 0.01:
        return False  # Ya normalizado
    
    # Convertir cada parte
    for part in parts_list:
        convertir_vertices_parte_a_grosor_maximo(blob, part.part_offset, grosor_actual)
    
    # Actualizar header a grosor máximo
    escribir_grosor_maximo(blob)
    
    return True  # Normalización realizada


def preparar_parte_externa_para_insercion(part_data: bytes, grosor_origen: Tuple[float, float, float]) -> bytearray:
    """
    Convierte una parte externa (ya extraída) a grosor máximo.
    
    Args:
        part_data: Bytes de la parte.
        grosor_origen: Tupla (gx, gy, gz) del PMDL de origen.
        
    Returns:
        Bytearray de la parte con vértices convertidos.
    """
    part_blob = bytearray(part_data)
    convertir_vertices_parte_a_grosor_maximo(part_blob, 0, grosor_origen)
    return part_blob


def normalizar_subparte(vertices_raw: bytearray, 
                        num_vertices: int, 
                        num_bones: int,
                        grosor_origen: Tuple[float, float, float]) -> bytearray:

    gx, gy, gz = grosor_origen
    
    # Calcular factores de escala
    factor_x = gx / GROSOR_MAXIMO if gx > 0 else 1.0
    factor_y = gy / GROSOR_MAXIMO if gy > 0 else 1.0
    factor_z = gz / GROSOR_MAXIMO if gz > 0 else 1.0
    
    # Si ya está en grosor máximo, retornar sin cambios
    if abs(factor_x - 1.0) < 0.01 and abs(factor_y - 1.0) < 0.01 and abs(factor_z - 1.0) < 0.01:
        return vertices_raw
    
    # Crear copia
    resultado = bytearray(vertices_raw)
    
    # Calcular tamaño de cada vértice
    tamaño_pesos = num_bones * 2
    tamaño_vertice = tamaño_pesos + 2 + 6
    
    # Procesar cada vértice
    for v in range(num_vertices):
        pos_coords = (v * tamaño_vertice) + tamaño_pesos + 2
        
        # Leer coordenadas actuales (int16)
        cx = struct.unpack_from("<h", resultado, pos_coords)[0]
        cy = struct.unpack_from("<h", resultado, pos_coords + 2)[0]
        cz = struct.unpack_from("<h", resultado, pos_coords + 4)[0]
        
        # Aplicar factor de escala
        cx = max(-32768, min(32767, int(round(cx * factor_x))))
        cy = max(-32768, min(32767, int(round(cy * factor_y))))
        cz = max(-32768, min(32767, int(round(cz * factor_z))))
        
        # Escribir coordenadas convertidas
        struct.pack_into("<h", resultado, pos_coords, cx)
        struct.pack_into("<h", resultado, pos_coords + 2, cy)
        struct.pack_into("<h", resultado, pos_coords + 4, cz)
    
    return resultado