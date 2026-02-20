def find_island_vertices(start_idx, uv_data):
    island = set()
    to_visit = {start_idx}
    
    while to_visit:
        idx = to_visit.pop()
        if idx in island:
            continue
        island.add(idx)
        
        # Agregar todos los vértices conectados por edges
        for li in uv_data[idx]['lines']:
            other_idx = li['other_idx']
            # Encontrar el índice global del otro vértice
            for global_idx, d in enumerate(uv_data):
                if (d['vertices_list'] is uv_data[idx]['vertices_list'] and
                    d['vertex_index'] == other_idx):
                    if global_idx not in island:
                        to_visit.add(global_idx)
    
    return island


def get_face_vertices(face_index, tri_data, uv_data):
    if face_index >= len(tri_data):
        return []
    
    ia, ib, ic = tri_data[face_index]
    if ia >= len(uv_data) or ib >= len(uv_data) or ic >= len(uv_data):
        return []
    
    return [ia, ib, ic]


def get_edge_vertices(edge_map, line_id):
    if line_id not in edge_map:
        return (None, None)
    
    ds, de = edge_map[line_id]
    return (ds, de)