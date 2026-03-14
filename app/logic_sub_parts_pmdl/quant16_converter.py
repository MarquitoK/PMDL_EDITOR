TABLE = [
    (0.0, 0x0080),
    (0.1, 0x0c74),
    (0.2, 0x1967),
    (0.3, 0x265a),
    (0.4, 0x334d),
    (0.5, 0x4040),
    (0.6, 0x4c34),
    (0.7, 0x5927),
    (0.8, 0x661a),
    (0.9, 0x730d),
    (1.0, 0x8000),
]

ESCALA = 1/64

def float_to_game16(value: float) -> int:
    value = max(0.0, min(1.0, value))

    # caso exacto
    for f, h in TABLE:
        if abs(value - f) < 1e-6:
            return h

    # buscar tramo
    for i in range(len(TABLE) - 1):
        f0, h0 = TABLE[i]
        f1, h1 = TABLE[i+1]

        if f0 <= value <= f1:
            t = (value - f0) / (f1 - f0)
            return round(h0 + (h1 - h0) * t)

    return TABLE[-1][1]

import struct

def game16_to_float(value: int) -> float:
    if value <= TABLE[0][1]:
        return round(struct.unpack('f', struct.pack('f', TABLE[0][0]))[0], 2)

    if value >= TABLE[-1][1]:
        return round(struct.unpack('f', struct.pack('f', TABLE[-1][0]))[0], 2)

    for i in range(len(TABLE) - 1):
        f0, h0 = TABLE[i]
        f1, h1 = TABLE[i+1]

        if h0 <= value <= h1:
            t = (value - h0) / (h1 - h0)
            result = f0 + (f1 - f0) * t
            return round(struct.unpack('f', struct.pack('f', result))[0], 2)

    return struct.unpack('f', struct.pack('f', 1.0))[0]

def procesar_uv(vertices:list, to_float = True):
    ESCALA_UV = 1.0 / 255.0
    for v in vertices:
        if to_float:
            v["uv"][0] *= ESCALA_UV
            v["uv"][1] *= ESCALA_UV
        else:
            v["uv"][0] = int(v["uv"][0] * 255.0)
            v["uv"][1] = int(v["uv"][1] * 255.0)

def procesar_vertices(grosor, escala:float, vertices:list, to_float = True):
    GROSOR_MAXIMO: float = 512.0

    grosor_x = grosor[0] if grosor[0] > 0 else GROSOR_MAXIMO
    grosor_y = grosor[1] if grosor[1] > 0 else GROSOR_MAXIMO
    grosor_z = grosor[2] if grosor[2] > 0 else GROSOR_MAXIMO

    factor_x = grosor_x / GROSOR_MAXIMO
    factor_y = grosor_y / GROSOR_MAXIMO
    factor_z = grosor_z / GROSOR_MAXIMO

    for v in vertices:
        if to_float:
            x = struct.unpack('f', struct.pack('f',
                v['pos'][0] * escala * factor_x
            ))[0]

            z = struct.unpack('f', struct.pack('f',
                -v['pos'][1] * escala * factor_y
            ))[0]
            y = struct.unpack('f', struct.pack('f',
                v['pos'][2] * escala * factor_z
            ))[0]
        else:
             x = int(v['pos'][0] / (escala * factor_x))
             z = int(v['pos'][1] / (escala * factor_y))
             y = int(-v['pos'][2] / (escala * factor_z))

        v['pos'] = [x, y, z]

def procesar_pesos(vertices:list, to_float = True):
    bones = []
    for v in vertices:
        bones = []
        for w in v['weights']:
            # print(w)
            if to_float:
                if w != 0:
                    value = game16_to_float(w)
                    value = round(value, 1)  # limitar a 1 decimal
                    bones.append(value)
                else:
                    bones.append("N/A")
            else:
                bones.append(
                    0 if str(w).strip().lower() == "n/a" or not str(w).strip()
                    else float_to_game16(round(float(w), 1))
                )
        # print(bones)
        v["weights"] = bones