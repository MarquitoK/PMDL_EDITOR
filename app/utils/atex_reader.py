from PIL import Image


ATEX_HEADER_SIZE  = 0x80
ATEX_INDICES_SIZE = 0x10000   # 256×256
ATEX_PALETTE_SIZE = 0x400     # 256 × 4 bytes
ATEX_MIN_SIZE     = ATEX_HEADER_SIZE + ATEX_INDICES_SIZE + ATEX_PALETTE_SIZE


def atex_to_pil(data: bytes) -> Image.Image:
    if len(data) < ATEX_MIN_SIZE:
        raise ValueError(
            f"Datos ATEX demasiado cortos: se esperan al menos "
            f"{ATEX_MIN_SIZE} bytes, hay {len(data)}."
        )

    indices_offset = ATEX_HEADER_SIZE
    palette_offset = ATEX_HEADER_SIZE + ATEX_INDICES_SIZE

    # Leer paleta
    palette = []
    for i in range(256):
        po = palette_offset + i * 4
        palette.append((data[po], data[po + 1], data[po + 2]))

    # Reconstruir imagen 256×256 con el algoritmo de tiling del juego
    img = Image.new("RGB", (256, 256))
    pixels = img.load()

    num  = 0
    num2 = 0
    num3 = 0
    num4 = 32

    while num4 != 0:
        num5 = 16
        while num5 != 0:
            num6 = 0
            while num6 < 8:
                num7 = 0
                while num7 < 16:
                    if num3 < 65536:
                        idx = indices_offset + num3
                        if idx < len(data):
                            color_index = data[idx]
                            color = palette[color_index] if color_index < len(palette) else (0, 0, 0)
                            x = int(num7 + num)
                            y = int(num6 + num2)
                            if x < 256 and y < 256:
                                pixels[x, y] = color
                        num3 += 1
                    num7 += 1
                num6 += 1
            if num + 2 < 256:
                num += 16
            num5 -= 1
        if num2 + 2 < 256:
            num2 += 8
        num = 0
        num4 -= 1

    return img


def atex_file_to_pil(filepath: str) -> Image.Image:
    with open(filepath, "rb") as f:
        data = f.read()
    return atex_to_pil(data)
