import numpy as np


def merge_vertices_by_distance(vertices, uvs, triangulos, threshold=0.00001):
    """Fusiona vértices duplicados considerando posición Y UVs"""
    if len(vertices) == 0:
        return vertices, uvs, triangulos
    
    vertices = np.array(vertices)
    uvs = np.array(uvs)
    
    # Mapeo de índices viejos a nuevos
    vertex_map = {}
    new_vertices = []
    new_uvs = []
    
    for i, vertex in enumerate(vertices):
        # Buscar si ya existe un vértice cercano CON UVs similares
        found = False
        for j, new_vertex in enumerate(new_vertices):
            # Distancia en posición 3D
            pos_dist = np.linalg.norm(vertex - new_vertex)
            
            # Distancia en UVs
            uv_dist = np.linalg.norm(uvs[i] - new_uvs[j])
            
            # Solo fusionar si AMBOS están cerca (posición Y UVs)
            if pos_dist < threshold and uv_dist < 0.01:
                vertex_map[i] = j
                found = True
                break
        
        if not found:
            vertex_map[i] = len(new_vertices)
            new_vertices.append(vertex)
            new_uvs.append(uvs[i])
    
    # Remapear triángulos
    new_triangulos = []
    for tri in triangulos:
        new_tri = [vertex_map[tri[0]], vertex_map[tri[1]], vertex_map[tri[2]]]
        # Evitar triángulos degenerados
        if new_tri[0] != new_tri[1] and new_tri[1] != new_tri[2] and new_tri[0] != new_tri[2]:
            new_triangulos.append(new_tri)
    
    return new_vertices, new_uvs, new_triangulos