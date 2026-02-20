import struct


def leer_uint32(blob, offset):
    return struct.unpack_from("<I", blob, offset)[0]

def leer_uint16(blob, offset):
    return struct.unpack_from("<H", blob, offset)[0]

def leer_uint8(blob, offset):
    return blob[offset]

def leer_int16(blob, offset):
    return struct.unpack_from("<h", blob, offset)[0]

def leer_float32(blob, offset):
    return struct.unpack_from("<f", blob, offset)[0]

def leer_vertices(datos_parte, offset_subparte, num_vertices, num_huesos):
    vertices = []
    tamaño_pesos = num_huesos * 2
    tamaño_vertice = tamaño_pesos + 2 + 6
    pos = offset_subparte
    
    for i in range(num_vertices):
        if pos + tamaño_vertice > len(datos_parte):
            break
        
        pos += tamaño_pesos
        uv_x = leer_uint8(datos_parte, pos)
        uv_y = leer_uint8(datos_parte, pos + 1)
        pos += 2
        
        coord_x = leer_int16(datos_parte, pos)
        coord_y = leer_int16(datos_parte, pos + 2)
        coord_z = leer_int16(datos_parte, pos + 4)
        pos += 6
        
        vertices.append({
            'indice': i, 'uv_x': uv_x, 'uv_y': uv_y,
            'coord_x': coord_x, 'coord_y': coord_y, 'coord_z': coord_z
        })
    
    return vertices

def analizar_subpartes(datos_parte):
    if len(datos_parte) < 4:
        return []
    
    cantidad_subpartes = leer_uint32(datos_parte, 0x00)
    subpartes = []
    
    for i in range(cantidad_subpartes):
        entrada_offset = 0x04 + (i * 0x10)
        if entrada_offset + 0x10 > len(datos_parte):
            break
        
        num_vertices = leer_uint16(datos_parte, entrada_offset + 0x00)
        num_huesos = leer_uint16(datos_parte, entrada_offset + 0x02)
        offset_subparte = leer_uint32(datos_parte, entrada_offset + 0x0C)
        vertices = leer_vertices(datos_parte, offset_subparte, num_vertices, num_huesos)
        
        subpartes.append({
            'indice': i, 'num_vertices': num_vertices,
            'num_huesos': num_huesos, 'offset': offset_subparte,
            'vertices': vertices
        })
    
    return subpartes

def analizar_pmdl(filepath):
    with open(filepath, 'rb') as f:
        blob = f.read()
    
    firma = blob[0:4].decode('ascii', errors='ignore')
    if firma not in ('pMdl', 'pMdF'):
        return None, "Error: No es un archivo PMDL/PMDF válido"
    
    info = {}
    import os
    info['nombre'] = os.path.basename(filepath)
    info['tipo'] = firma
    info['huesos'] = blob[0x08]
    info['grosor_x'] = leer_float32(blob, 0x40)
    info['grosor_y'] = leer_float32(blob, 0x44)
    info['grosor_z'] = leer_float32(blob, 0x48)
    info['offset_huesos'] = leer_uint32(blob, 0x50)
    info['cantidad_partes'] = leer_uint32(blob, 0x5C)
    info['offset_indice_partes'] = leer_uint32(blob, 0x60)
    
    partes = []
    for i in range(info['cantidad_partes']):
        entrada_offset = info['offset_indice_partes'] + (i * 0x20)
        if entrada_offset + 0x20 > len(blob):
            break
        
        capa = leer_uint16(blob, entrada_offset + 0x00)
        opacidad = leer_uint16(blob, entrada_offset + 0x02)
        part_offset = leer_uint32(blob, entrada_offset + 0x04)
        part_length = leer_uint32(blob, entrada_offset + 0x08)
        flag_especial = leer_uint32(blob, entrada_offset + 0x0C)
        
        datos_parte = blob[part_offset : part_offset + part_length]
        subpartes = analizar_subpartes(datos_parte)
        
        partes.append({
            'indice': i, 'capa': capa, 'opacidad': opacidad,
            'offset': part_offset, 'longitud': part_length,
            'flag_especial': flag_especial, 'subpartes': subpartes,
            'cantidad_subpartes': len(subpartes)
        })
    
    info['partes'] = partes
    return info, None