import json
import struct
import copy
from collections import defaultdict, deque
from pathlib import Path
from app.binary_builder.triangle_strip import find_strip
from app.logic_sub_parts_pmdl.operations import align_16, replace_id_ff
from app.logic_sub_parts_pmdl.quant16_converter import game16_to_float, float_to_game16, procesar_pesos, \
    procesar_vertices, ESCALA
from app.utils.part_header import exportar_parte_con_encabezado

DEBUG=False


class MeshBinaryBuilder:
    def __init__(self):
        self.path = None
        self.escala = ESCALA
        self.subparts_dict = []
        self.grosor = [512.0, 512.0, 512.0]
        self.subpartes_v_ordenado = []
        self.strips_dict = {}

    def separar_modelo_json(self, input_path, max_tris=22):
        self.subparts_dict = []
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not data["type"] == "part":
                raise ValueError(f"El archivo {self.path.name} no es tipo part o no contiene un modelo 3D")

        vertices = data["vertices"]
        faces = data["faces"]
        id_bones = data.get("id_bones", [])

        # -------------------------------------------------
        # 1. Construir mapa arista -> caras
        # -------------------------------------------------
        edge_map = defaultdict(list)

        for fi, face in enumerate(faces):
            for i in range(3):
                edge = tuple(sorted((face[i], face[(i + 1) % 3])))
                edge_map[edge].append(fi)

        # -------------------------------------------------
        # 2. Construir grafo de adyacencia
        # -------------------------------------------------
        adjacency = defaultdict(set)

        for edge, face_indices in edge_map.items():
            if len(face_indices) > 1:
                for i in range(len(face_indices)):
                    for j in range(i + 1, len(face_indices)):
                        a = face_indices[i]
                        b = face_indices[j]
                        adjacency[a].add(b)
                        adjacency[b].add(a)

        # -------------------------------------------------
        # 3. Encontrar componentes con límite opcional
        # -------------------------------------------------
        visited = set()
        subparts = []

        for i in range(len(faces)):
            if i in visited:
                continue

            queue = deque([i])

            while queue:
                component = []
                local_queue = deque()

                f = queue.popleft()
                if f in visited:
                    continue

                local_queue.append(f)

                while local_queue and (max_tris is None or len(component) < max_tris):
                    current = local_queue.popleft()

                    if current in visited:
                        continue

                    visited.add(current)
                    component.append(current)

                    for neighbor in adjacency[current]:
                        if neighbor not in visited:
                            local_queue.append(neighbor)

                subparts.append(component)

        if DEBUG:
            print(f"Se generaron {len(subparts)} subpartes.")

        # -------------------------------------------------
        # 4. Crear JSON por subparte
        # -------------------------------------------------
        for idx, face_indices in enumerate(subparts):
            used_vertices = set()
            new_faces = []

            # recolectar vértices usados
            for fi in face_indices:
                face = faces[fi]
                new_faces.append(face)
                used_vertices.update(face)

            used_vertices = sorted(list(used_vertices))

            # mapa de reindexación
            vert_map = {old_i: new_i for new_i, old_i in enumerate(used_vertices)}

            # reconstruir lista de vértices
            new_vertices = []
            for new_i, old_i in enumerate(used_vertices):
                v = vertices[old_i].copy()
                v["id_v"] = str(new_i)
                new_vertices.append(v)

            # reconstruir caras con nuevos índices
            remapped_faces = []
            for face in new_faces:
                remapped_faces.append([
                    vert_map[face[0]],
                    vert_map[face[1]],
                    vert_map[face[2]]
                ])

            # -------------------------------------------------
            # 5. Filtrar bones no usados
            # -------------------------------------------------
            bone_count = len(id_bones)
            used_bones_mask = [False] * bone_count

            # Detectar qué columnas tienen peso real
            for v in new_vertices:
                for i, w in enumerate(v["weights"]):
                    if isinstance(w, (int, float)):
                        used_bones_mask[i] = True

            # Crear nuevo id_bones filtrado
            filtered_id_bones = []
            index_remap = {}

            new_index = 0
            for i, used in enumerate(used_bones_mask):
                if used:
                    filtered_id_bones.append(id_bones[i])
                    index_remap[i] = new_index
                    new_index += 1

            # Actualizar weights en cada vértice
            for v in new_vertices:
                new_weights = []
                for i, w in enumerate(v["weights"]):
                    if i in index_remap:
                        new_weights.append(w)
                v["weights"] = new_weights

            # Reemplazar id_bones
            id_bones_final = filtered_id_bones

            output_data = {
                "id_bones": id_bones_final,
                "vertices": new_vertices,
                "faces": remapped_faces
            }

            self.subparts_dict.append(output_data)
        if DEBUG:
            print("Parte dividida.")

    def build_subpartes(self, file_path: Path | str, max_tris: int):
        self.separar_modelo_json(
            input_path=file_path,
            max_tris=max_tris  # afecta la cantidad de subpartes
        )

        self.subpartes_v_ordenado = []
        if DEBUG: print("buscando strip")
        # self.strips_dict = self.calcular_strips_paralelo()

        for i, subpart in enumerate(self.subparts_dict):
            strip = find_strip(subpart["faces"])
            # strip = self.strips_dict[i]

            pos_vertex = []

            data = {
                "type": "subpart",
                "grosor": [512.0, 512.0, 512.0],
                "id_bones": copy.deepcopy(subpart["id_bones"]),
                "unk": 302007041
            }

            # ordena los vertices
            for st in strip:
                pos_vertex.append(copy.deepcopy(subpart["vertices"][st]))

            data["vertices"] = pos_vertex
            procesar_vertices(self.grosor, self.escala, data["vertices"], False)
            procesar_pesos(data["vertices"], False)
            self.subpartes_v_ordenado.append(copy.deepcopy(data))
            if DEBUG:
                print(f"vertices ordenados subparte: {i + 1}")

    def sort_subparts(self, lista):
        def sort_key(item):
            bones = [int(b, 16) for b in item["id_bones"]]
            padded = bones + [-1] * (4 - len(bones))
            return tuple(padded)

        return sorted(lista, key=sort_key)

    def build_part(self, subparts: list[dict]) -> bytearray:
        num_subparts = len(subparts)
        size_header = 48 + (num_subparts*0x10)
        data_part = bytearray()
        data_part += struct.pack("<I", num_subparts)
        out = bytearray()
        for subpart in subparts:
            data_part += struct.pack("<H", len(subpart["vertices"]))
            data_part += struct.pack("<H", len(subpart["id_bones"]))

            ids_int = [int(x, 16) for x in subpart["id_bones"]]
            ids = (ids_int + [0, 0, 0, 0])[:4]
            data_part += struct.pack("<4B", *ids)

            data_part += struct.pack("<I", subpart["unk"])

            # posicion de la subparte
            data_part += struct.pack("<I", size_header + len(out))

            # subpart["vertices"] = _procesar_vertices(subpart["vertices"], subpart["grosor"], ESCALA, False)
            # subpart["vertices"] = _procesar_pesos(subpart["vertices"], False)

            for v in subpart["vertices"]:

                # ---- weights  (>H)
                for w in v["weights"]:
                    out += struct.pack(">H", w)

                # ---- uv (<B)
                for uv in v["uv"]:
                    out += struct.pack("<B", uv)

                # ---- pos (<h)
                for p in v["pos"]:
                    out += struct.pack("<h", p)


        data_part += bytearray(44)
        data_part += out

        return data_part

    # def _procesar_vertices(self, vertices: list, to_float=True):
    #     GROSOR_MAXIMO = 68.0
    #
    #     grosor_x = self.grosor[0] if self.grosor[0] > 0 else GROSOR_MAXIMO
    #     grosor_y = self.grosor[1] if self.grosor[1] > 0 else GROSOR_MAXIMO
    #     grosor_z = self.grosor[2] if self.grosor[2] > 0 else GROSOR_MAXIMO
    #
    #     factor_x = grosor_x / GROSOR_MAXIMO
    #     factor_y = grosor_y / GROSOR_MAXIMO
    #     factor_z = grosor_z / GROSOR_MAXIMO
    #
    #     for v in vertices:
    #         if to_float:
    #             x = struct.unpack('f', struct.pack('f',
    #                                                v['pos'][0] * self.escala * factor_x * -1.0
    #                                                ))[0]
    #
    #             y = struct.unpack('f', struct.pack('f',
    #                                                v['pos'][1] * self.escala * factor_y * -1.0
    #                                                ))[0]
    #             z = struct.unpack('f', struct.pack('f',
    #                                                v['pos'][2] * self.escala * factor_z
    #                                                ))[0]
    #         else:
    #             x = int(-v['pos'][0] / (self.escala * factor_x))
    #             y = int(-v['pos'][1] / (self.escala * factor_y))
    #             z = int(v['pos'][2] / (self.escala * factor_z))
    #
    #         v['pos'] = [x, y, z]
    #
    # def _procesar_pesos(self, vertices: list, to_float=True):
    #     bones = []
    #     for v in vertices:
    #         bones = []
    #         for w in v['weights']:
    #             if to_float:
    #                 bones.append(game16_to_float(w) if w != 0 else "N/A")
    #             else:
    #                 bones.append(0 if str(w).strip().lower() == "n/a" or not str(w).strip() else float_to_game16(float(w)))
    #         v["weights"] = bones

    def make_part(self, path: Path | str, max_tris: int):
        self.path = path if type(path) == Path else Path(path)
        self.build_subpartes(self.path, max_tris)
        self.subpartes_v_ordenado = self.sort_subparts(self.subpartes_v_ordenado)

        parte_ttt = self.build_part(self.subpartes_v_ordenado)
        # padding
        align_16(parte_ttt)
        parte_ttt += bytearray(0x10)

        with open(self.path.with_suffix(".tttpart"), "wb") as f:
            # guardar con id ff y header con grosor max
            replace_id_ff(part=parte_ttt, reemp=False)
            part_header = exportar_parte_con_encabezado(parte_ttt, self.grosor[0], self.grosor[1], self.grosor[2], 1,  65535, 0)
            f.write(part_header)
            if DEBUG:
                print("parte ttt generada")

