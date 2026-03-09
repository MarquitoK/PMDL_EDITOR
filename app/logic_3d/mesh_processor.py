import numpy as np


def merge_vertices_by_distance(vertices, uvs, triangulos, threshold=0.00001):
    if len(vertices) == 0:
        return vertices, uvs, triangulos

    vertices = np.array(vertices, dtype=np.float32)
    uvs      = np.array(uvs,      dtype=np.float32)

    uv_tol  = 0.01
    scale_p = 1.0 / max(threshold, 1e-9)
    scale_u = 1.0 / uv_tol

    index_map = {}
    new_vertices = []
    new_uvs      = []
    vertex_map   = {}

    for i in range(len(vertices)):
        kx = int(round(float(vertices[i][0]) * scale_p))
        ky = int(round(float(vertices[i][1]) * scale_p))
        kz = int(round(float(vertices[i][2]) * scale_p))
        ku = int(round(float(uvs[i][0])      * scale_u))
        kv = int(round(float(uvs[i][1])      * scale_u))
        key = (kx, ky, kz, ku, kv)

        if key in index_map:
            vertex_map[i] = index_map[key]
        else:
            j = len(new_vertices)
            index_map[key] = j
            vertex_map[i]  = j
            new_vertices.append(vertices[i])
            new_uvs.append(uvs[i])

    new_triangulos = []
    for tri in triangulos:
        a, b, c = vertex_map[tri[0]], vertex_map[tri[1]], vertex_map[tri[2]]
        if a != b and b != c and a != c:
            new_triangulos.append([a, b, c])

    return new_vertices, new_uvs, new_triangulos