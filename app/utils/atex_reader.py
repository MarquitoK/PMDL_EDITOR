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


def pil_to_atex(img: Image.Image, original_header: bytes) -> bytes:
    if img.size != (256, 256):
        raise ValueError("La imagen debe ser exactamente 256×256 píxeles.")

    img = img.convert("RGB")
    pixels = img.load()

    # Paso 1: construir paleta recorriendo píxeles en orden lineal (replicando ReadTex del C#)
    # El color en slot 0 queda reservado; se empieza a agregar desde slot 1 igual que el original
    palette_rgb = [(0, 0, 0)] * 256
    color_to_index = {}
    next_slot = 1  # slot 0 queda en negro por defecto

    for y in range(256):
        for x in range(256):
            c = pixels[x, y]
            if c not in color_to_index:
                if next_slot >= 256:
                    break
                color_to_index[c] = next_slot
                palette_rgb[next_slot] = c
                next_slot += 1
        else:
            continue
        break

    # Paso 2: escribir índices con el algoritmo de tiling (igual que ReadTex segunda parte)
    indices = bytearray(ATEX_INDICES_SIZE)
    num5 = 0
    num6 = 0
    num7 = 0
    num8 = 32

    while num8 != 0:
        num9 = 16
        while num9 != 0:
            num10 = 0
            while num10 < 8:
                num11 = 0
                while num11 < 16:
                    if num5 < 65536:
                        c = pixels[num11 + num6, num10 + num7]
                        indices[num5] = color_to_index.get(c, 0)
                        num5 += 1
                    num11 += 1
                num10 += 1
            if num6 + 2 < 256:
                num6 += 16
            num9 -= 1
        if num7 + 2 < 256:
            num7 += 8
        num6 = 0
        num8 -= 1

    # Paso 3: serializar paleta con alpha=0x80 por entrada (igual que el formato ATEX original)
    palette_bytes = bytearray(ATEX_PALETTE_SIZE)
    for i in range(256):
        r, g, b = palette_rgb[i]
        palette_bytes[i * 4 + 0] = r
        palette_bytes[i * 4 + 1] = g
        palette_bytes[i * 4 + 2] = b
        palette_bytes[i * 4 + 3] = 0x80

    return bytes(original_header) + bytes(indices) + bytes(palette_bytes)


def png_to_atex(png_path: str, original_header: bytes) -> bytes:
    import os as _os
    if _os.path.splitext(png_path)[1].lower() != ".png":
        raise ValueError("Solo se permiten archivos PNG.")
    img = Image.open(png_path).convert("RGB")
    if img.size != (256, 256):
        raise ValueError("La imagen debe ser exactamente 256×256 píxeles.")
    return pil_to_atex(img, original_header)