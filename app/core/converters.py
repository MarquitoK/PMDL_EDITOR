"""
Conversores de opacidad entre porcentaje (0-100) y valor uint16 (0x0000-0xFFFF).
"""

def percent_from_opacity_u16(u16: int) -> int:
    """Convierte un valor de opacidad uint16 a porcentaje."""
    if u16 <= 0:
        return 0
    if u16 >= 0xFFFF:
        return 100
    return round(u16 * 100 / 0xFFFF)


def opacity_u16_from_percent(pct: int) -> int:
    """Convierte un porcentaje a valor de opacidad uint16."""
    pct = max(0, min(100, int(pct)))
    if pct == 100:
        return 0xFFFF
    if pct == 0:
        return 0x0000
    return int(round(pct * 0xFFFF / 100.0))