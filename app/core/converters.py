def percent_from_opacity_u16(u16: int) -> int:
    low_byte = u16 & 0xFF
    if low_byte <= 0:
        return 100
    return round(low_byte * 100 / 0xFF)


def opacity_u16_from_percent(pct) -> int:
    pct = max(1, min(100, int(round(float(pct)))))
    low_byte = round(pct * 0xFF / 100)
    low_byte = max(1, min(0xFF, low_byte))
    return low_byte & 0xFFFF