import numpy as np
from OpenGL.GL import *
import hashlib


def _get_bone_color(bone_id):
    """Genera un color consistente basado en bone_id."""
    hash_obj   = hashlib.md5(str(bone_id).encode())
    hash_bytes = hash_obj.digest()
    r = hash_bytes[0] / 255.0
    g = hash_bytes[1] / 255.0
    b = hash_bytes[2] / 255.0
    return (r, g, b, 0.75)


def draw_bone_pyramid(head, tail, bone_id, is_selected):
    head = np.array(head, dtype=np.float64)
    tail = np.array(tail, dtype=np.float64)

    direction = tail - head
    length    = np.linalg.norm(direction)

    if length < 0.0001:
        length    = 0.05
        direction = np.array([0.0, length, 0.0])
    else:
        direction = direction / length

    width = length * 0.12   # ancho relativo a la longitud del hueso

    # Dos vectores perpendiculares a la dirección
    up   = np.array([0.0, 1.0, 0.0])
    perp = np.cross(direction, up)
    if np.linalg.norm(perp) < 0.0001:
        up   = np.array([1.0, 0.0, 0.0])
        perp = np.cross(direction, up)
    perp  = perp / np.linalg.norm(perp) * width
    perp2 = np.cross(direction, perp)
    if np.linalg.norm(perp2) > 0.0001:
        perp2 = perp2 / np.linalg.norm(perp2) * width

    # Base de la pirámide centrada en head, ligeramente desplazada hacia tail
    base_center = head + direction * (length * 0.1)
    base1 = base_center + perp
    base2 = base_center + perp2
    base3 = base_center - perp
    base4 = base_center - perp2

    color = (1.0, 0.8, 0.0, 0.95) if is_selected else _get_bone_color(bone_id)

    glDisable(GL_LIGHTING)
    glColor4f(*color)

    # Cuatro caras triangulares hacia la punta (tail)
    glBegin(GL_TRIANGLES)
    for a, b in [(base1, base2), (base2, base3), (base3, base4), (base4, base1)]:
        glVertex3fv(tail)
        glVertex3fv(a)
        glVertex3fv(b)
    # Tapa de la base (cuadrado dividido en 2 triángulos)
    glVertex3fv(base1); glVertex3fv(base3); glVertex3fv(base2)
    glVertex3fv(base1); glVertex3fv(base4); glVertex3fv(base3)
    glEnd()

    # Borde amarillo si está seleccionado
    if is_selected:
        glLineWidth(2.5)
        glColor3f(1.0, 0.95, 0.0)
        glBegin(GL_LINE_LOOP)
        glVertex3fv(base1); glVertex3fv(base2)
        glVertex3fv(base3); glVertex3fv(base4)
        glEnd()
        glBegin(GL_LINES)
        for base in (base1, base2, base3, base4):
            glVertex3fv(tail); glVertex3fv(base)
        glEnd()
        glLineWidth(1.0)