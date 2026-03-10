"""
Conversores de opacidad entre porcentaje (0-100) y valor uint16 (0x0000-0xFFFF).
"""

def percent_from_opacity_u16(u16: int) -> float:
    if u16 <= 0:
        return 0.0
    if u16 >= 0xFFFF:
        return 100.0
    return round(u16 * 100 / 0xFFFF, 1)


def opacity_u16_from_percent(pct) -> int:
    pct = max(0.0, min(100.0, float(pct)))
    if pct >= 100.0:
        return 0xFFFF
    if pct <= 0.0:
        return 0x0000
    return int(round(pct * 0xFFFF / 100.0))