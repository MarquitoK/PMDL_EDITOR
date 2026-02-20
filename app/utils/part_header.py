import struct
from typing import Tuple, Optional


FIRMA_PART = b"PART"
TAMAÑO_ENCABEZADO = 32


def crear_encabezado_parte(grosor_x: float, grosor_y: float, grosor_z: float,
                           capa: int, opacidad: int, flag: int) -> bytes:

    encabezado = bytearray(TAMAÑO_ENCABEZADO)
    
    # Firma
    encabezado[0:4] = FIRMA_PART
    
    # Grosor (3 floats)
    struct.pack_into("<f", encabezado, 0x0C, grosor_x)
    struct.pack_into("<f", encabezado, 0x10, grosor_y)
    struct.pack_into("<f", encabezado, 0x14, grosor_z)
    
    # Capa (uint16)
    struct.pack_into("<H", encabezado, 0x18, capa & 0xFFFF)
    
    # Opacidad (uint16)
    struct.pack_into("<H", encabezado, 0x1A, opacidad & 0xFFFF)
    
    # Flag (uint32)
    struct.pack_into("<I", encabezado, 0x1C, flag & 0xFFFFFFFF)
    
    return bytes(encabezado)


def exportar_parte_con_encabezado(part_data: bytes, grosor_x: float, grosor_y: float, grosor_z: float,
                                  capa: int, opacidad: int, flag: int) -> bytes:

    encabezado = crear_encabezado_parte(grosor_x, grosor_y, grosor_z, capa, opacidad, flag)
    return encabezado + part_data


def tiene_encabezado(data: bytes) -> bool:
    if len(data) < 4:
        return False
    return data[0:4] == FIRMA_PART


def leer_encabezado_parte(data: bytes) -> Optional[dict]:
    if not tiene_encabezado(data):
        return None
    
    if len(data) < TAMAÑO_ENCABEZADO:
        raise ValueError("Encabezado incompleto en los datos de la parte.")
    
    # Leer grosor (3 floats)
    grosor_x = struct.unpack_from("<f", data, 0x0C)[0]
    grosor_y = struct.unpack_from("<f", data, 0x10)[0]
    grosor_z = struct.unpack_from("<f", data, 0x14)[0]
    
    # Leer capa (uint16)
    capa = struct.unpack_from("<H", data, 0x18)[0]
    
    # Leer opacidad (uint16)
    opacidad = struct.unpack_from("<H", data, 0x1A)[0]
    
    # Leer flag (uint32)
    flag = struct.unpack_from("<I", data, 0x1C)[0]
    
    # Extraer datos de la parte
    part_data = data[TAMAÑO_ENCABEZADO:]
    
    return {
        'grosor_x': grosor_x,
        'grosor_y': grosor_y,
        'grosor_z': grosor_z,
        'capa': capa,
        'opacidad': opacidad,
        'flag': flag,
        'part_data': part_data
    }


def importar_parte_con_encabezado(data: bytes) -> Tuple[bytes, Optional[dict]]:
    if tiene_encabezado(data):
        info = leer_encabezado_parte(data)
        return info['part_data'], {
            'grosor': (info['grosor_x'], info['grosor_y'], info['grosor_z']),
            'capa': info['capa'],
            'opacidad': info['opacidad'],
            'flag': info['flag']
        }
    else:
        return data, None
