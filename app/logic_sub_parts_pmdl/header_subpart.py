import struct

class SpartHeader:
    def __init__(self, x: float, y: float, z: float, dat_subpart: bytearray|bytes, vertices: bytearray|bytes):
        if len(dat_subpart) != 12:
            raise ValueError("dat_subpart debe tener exactamente 12 bytes")

        self.signature = b"SPART"
        self.grosor = (x, y, z)
        self.dat_subpart = dat_subpart
        self.vertices = vertices

    def build(self) -> bytearray:
        # tamaño mínimo: offset 0x30 + tamaño del bytearray final
        size = 0x30 + len(self.vertices)
        buffer = bytearray(size)

        # --- Firma ---
        buffer[0:5] = self.signature

        # --- Coordenadas en 0x10 ---
        # 3 floats little-endian
        struct.pack_into("<fff", buffer, 0x10, *self.grosor)

        # --- 12 bytes en 0x20 ---
        buffer[0x20:0x20+12] = self.dat_subpart

        # --- bytearray en 0x30 ---
        buffer[0x30:0x30+len(self.vertices)] = self.vertices

        return buffer

def comprobar_header_spart(
    buffer: bytearray
) -> tuple[
    tuple[float, float, float],  # grosor
    int,                          # nvertices
    int,                          # nbones
    tuple[int, int, int, int],    # idbones
    int,                          # unk
    bytearray                     # vertices
]:
    """
    Comprueba si tiene encabezado SPART y devuelve:
    (grosor, nvertices, nbones, idbones, unk, vertices)
    """

    if len(buffer) < 0x30:
        raise ValueError("buffer demasiado pequeño para header SPART")

    if buffer[0:5] != b"SPART":
        raise ValueError("la subparte no contiene el encabezado SPART")

    grosor = struct.unpack_from("<fff", buffer, 0x10)
    nvertices = struct.unpack_from("<H", buffer, 0x20)[0]
    nbones = struct.unpack_from("<H", buffer, 0x22)[0]
    idbones = struct.unpack_from("<4B", buffer, 0x24)
    unk = struct.unpack_from("<I", buffer, 0x28)[0]
    vertices = buffer[0x30:]

    return grosor, nvertices, nbones, idbones, unk, vertices