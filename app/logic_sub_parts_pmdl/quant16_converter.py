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

def game16_to_float(value: int) -> float:
    # clamp por seguridad
    if value <= TABLE[0][1]:
        return TABLE[0][0]
    if value >= TABLE[-1][1]:
        return TABLE[-1][0]

    # buscar tramo
    for i in range(len(TABLE) - 1):
        f0, h0 = TABLE[i]
        f1, h1 = TABLE[i+1]

        if h0 <= value <= h1:
            t = (value - h0) / (h1 - h0)
            return f0 + (f1 - f0) * t

    return 1.0