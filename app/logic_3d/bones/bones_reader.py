import struct


ESCALA_GLOBAL = 0.25
OFFSET_Y_GLOBAL = 0.0


def pmdl_a_visor(px, py, pz):
    # Mismo eje que el mesh: x=-X, y=-Y, z=+Z
    return (-px, -py, pz)


def leer_hueso(blob, offset):
    pop_level = struct.unpack_from('<I', blob, offset + 0x04)[0]
    bone_id   = blob[offset + 0x0A]

    px, py, pz = struct.unpack_from('<3f', blob, offset + 0x10)
    ppx, ppy, ppz = struct.unpack_from('<3f', blob, offset + 0x20)

    return {
        'bone_id'  : bone_id,
        'pop_level': pop_level,
        'pos'      : (px, py, pz),
        'pos_padre': (ppx, ppy, ppz),
    }


def construir_jerarquia(blob, offset_huesos, cantidad_huesos):
    huesos = []
    pila   = []   # pila de índices (no IDs)

    for i in range(cantidad_huesos):
        offset = offset_huesos + (i * 0xA0)
        if offset + 0xA0 > len(blob):
            break

        hueso = leer_hueso(blob, offset)

        # El padre es el tope actual de la pila
        padre_idx = pila[-1] if pila else None
        hueso['padre_idx'] = padre_idx
        hueso['idx']       = i

        huesos.append(hueso)

        # Apilar este hueso antes de aplicar el pop
        pila.append(i)

        # Aplicar pop_level: subir N niveles
        for _ in range(hueso['pop_level']):
            if pila:
                pila.pop()

    return huesos


def leer_armature_pmdl(blob):
    if len(blob) < 0x54:
        return []

    cantidad_huesos = struct.unpack_from('<I', blob, 0x08)[0]
    offset_huesos   = struct.unpack_from('<I', blob, 0x50)[0]

    if cantidad_huesos == 0 or offset_huesos == 0:
        return []

    huesos = construir_jerarquia(blob, offset_huesos, cantidad_huesos)

    # ── Mapa de hijos por índice ──────────────────────────────────────────
    hijos_de = {i: [] for i in range(len(huesos))}
    for h in huesos:
        if h['padre_idx'] is not None:
            hijos_de[h['padre_idx']].append(h['idx'])

    # ── Calcular pos_visor y tail_visor ───────────────────────────────────
    LONGITUD_MINIMA = 0.03  # unidades del visor para huesos hoja/raíz

    for h in huesos:
        px, py, pz = h['pos']
        bx, by, bz = pmdl_a_visor(px, py, pz)
        h['pos_visor'] = (bx * ESCALA_GLOBAL,
                          by * ESCALA_GLOBAL + OFFSET_Y_GLOBAL,
                          bz * ESCALA_GLOBAL)

    for h in huesos:
        idx      = h['idx']
        hijos    = hijos_de[idx]
        head     = h['pos_visor']

        if hijos:
            # tail = promedio de posiciones de todos los hijos directos
            sx, sy, sz = 0.0, 0.0, 0.0
            for hijo_idx in hijos:
                hx, hy, hz = huesos[hijo_idx]['pos_visor']
                sx += hx; sy += hy; sz += hz
            n = len(hijos)
            h['tail_visor'] = (sx / n, sy / n, sz / n)

        elif h['padre_idx'] is not None:
            # Hueso hoja: extender en la misma dirección padre→este
            padre_pos = huesos[h['padre_idx']]['pos_visor']
            dx = head[0] - padre_pos[0]
            dy = head[1] - padre_pos[1]
            dz = head[2] - padre_pos[2]
            length = (dx*dx + dy*dy + dz*dz) ** 0.5
            if length > 0.0001:
                # misma longitud que el segmento padre→este
                h['tail_visor'] = (head[0] + dx,
                                   head[1] + dy,
                                   head[2] + dz)
            else:
                h['tail_visor'] = (head[0], head[1] + LONGITUD_MINIMA, head[2])
        else:
            # Raíz sin hijos
            h['tail_visor'] = (head[0], head[1] + LONGITUD_MINIMA, head[2])

        # Seguridad: tail != head
        tail = h['tail_visor']
        if (tail[0] == head[0] and tail[1] == head[1] and tail[2] == head[2]):
            h['tail_visor'] = (head[0], head[1] + LONGITUD_MINIMA, head[2])

    return huesos


def _recalcular_tails(huesos):
    # Recalcula tail_visor usando pos_visor ya actualizado
    LONGITUD_MINIMA = 0.03
    hijos_de = {h['idx']: [] for h in huesos}
    for h in huesos:
        if h['padre_idx'] is not None:
            hijos_de[h['padre_idx']].append(h['idx'])

    for h in huesos:
        idx = h['idx']
        hijos = hijos_de[idx]
        head = h['pos_visor']

        if hijos:
            sx, sy, sz = 0.0, 0.0, 0.0
            for hijo_idx in hijos:
                hx, hy, hz = huesos[hijo_idx]['pos_visor']
                sx += hx; sy += hy; sz += hz
            n = len(hijos)
            h['tail_visor'] = (sx/n, sy/n, sz/n)
        elif h['padre_idx'] is not None:
            padre_pos = huesos[h['padre_idx']]['pos_visor']
            dx = head[0]-padre_pos[0]
            dy = head[1]-padre_pos[1]
            dz = head[2]-padre_pos[2]
            length = (dx*dx+dy*dy+dz*dz)**0.5
            if length > 0.0001:
                h['tail_visor'] = (head[0]+dx, head[1]+dy, head[2]+dz)
            else:
                h['tail_visor'] = (head[0], head[1]+LONGITUD_MINIMA, head[2])
        else:
            h['tail_visor'] = (head[0], head[1]+LONGITUD_MINIMA, head[2])

        tail = h['tail_visor']
        if tail[0]==head[0] and tail[1]==head[1] and tail[2]==head[2]:
            h['tail_visor'] = (head[0], head[1]+LONGITUD_MINIMA, head[2])


def cargar_nombres_huesos(filepath=None):
    if filepath is None:
        import os
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bones_list.txt')
    nombres = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                parts = line.split(':', 1)
                if len(parts) == 2:
                    nombres[parts[0].strip()] = parts[1].strip()
    except:
        pass
    return nombres