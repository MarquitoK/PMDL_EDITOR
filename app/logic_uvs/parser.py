import struct
import os


class PmdlParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.blob = None
        self.part_count = 0
        self.parts_index_offset = 0
        self.parts = []
        self.parts_data = []

    def load_file(self):
        try:
            with open(self.filepath, 'rb') as f:
                self.blob = f.read()
            return True
        except Exception as e:
            print(f"Error al cargar archivo: {e}")
            return False

    def parse_header(self):
        if len(self.blob) < 0x70:
            raise ValueError("Archivo muy pequeño para ser un PMDL válido")
        self.part_count = struct.unpack_from("<I", self.blob, 0x5C)[0]
        self.parts_index_offset = struct.unpack_from("<I", self.blob, 0x60)[0]
        print(f"\n{'='*80}")
        print(f"ARCHIVO: {os.path.basename(self.filepath)}")
        print(f"{'='*80}")
        print(f"Cantidad de partes: {self.part_count}")
        print(f"Offset del índice de partes: 0x{self.parts_index_offset:08X}")

    def parse_parts_index(self):
        self.parts = []
        for i in range(self.part_count):
            entrada_offset = self.parts_index_offset + (i * 0x20)
            if entrada_offset + 0x20 > len(self.blob):
                break
            part_offset = struct.unpack_from("<I", self.blob, entrada_offset + 0x04)[0]
            part_length = struct.unpack_from("<I", self.blob, entrada_offset + 0x08)[0]
            self.parts.append({
                'index': i,
                'offset': part_offset,
                'length': part_length,
                'end': part_offset + part_length
            })

    def get_part_data(self, part_index):
        if part_index >= len(self.parts):
            return None
        part = self.parts[part_index]
        if part['end'] > len(self.blob):
            return None
        return self.blob[part['offset']:part['end']]

    def parse_all_parts_uvs(self):
        self.parts_data = []
        for part_idx in range(len(self.parts)):
            self.parts_data.append(self.parse_part_uvs(part_idx))
        return self.parts_data

    def parse_part_uvs(self, part_index):
        part_data = self.get_part_data(part_index)
        if not part_data or len(part_data) < 4:
            return {'subparts': []}
        subpart_count = struct.unpack_from("<I", part_data, 0x00)[0]
        subparts = []
        for i in range(subpart_count):
            index_offset = 0x04 + (i * 0x10)
            if index_offset + 0x10 > len(part_data):
                break
            vertex_count   = struct.unpack_from("<H", part_data, index_offset)[0]
            bone_count     = struct.unpack_from("<H", part_data, index_offset + 0x02)[0]
            subpart_offset = struct.unpack_from("<I", part_data, index_offset + 0x0C)[0]
            vertices = self.parse_vertices_data(part_data, subpart_offset,
                                                vertex_count, bone_count)
            subparts.append({
                'index': i, 'vertex_count': vertex_count,
                'bone_count': bone_count, 'offset': subpart_offset,
                'vertices': vertices
            })
        return {'subparts': subparts}

    def parse_vertices_data(self, part_data, subpart_offset, vertex_count, bone_count):
        weight_size = bone_count * 2
        vertex_size = weight_size + 2 + 6
        vertices = []
        for v in range(vertex_count):
            vertex_offset = subpart_offset + (v * vertex_size)
            if vertex_offset + vertex_size > len(part_data):
                break
            uv_offset = vertex_offset + weight_size
            uv_x = struct.unpack_from("B", part_data, uv_offset)[0]
            uv_y = struct.unpack_from("B", part_data, uv_offset + 1)[0]
            vertices.append({'x': uv_x, 'y': uv_y})
        return vertices

    def analyze(self):
        if not self.load_file():
            return False
        try:
            self.parse_header()
            self.parse_parts_index()
            self.parse_all_parts_uvs()
            print(f"[OK] Analisis completado: {self.part_count} partes encontradas\n")
            return True
        except Exception as e:
            print(f"Error durante el análisis: {e}")
            return False

    def save_uvs(self, parts_data, output_path=None):
        # Guarda las coordenadas UV modificadas de vuelta al archivo PMDL
        if output_path is None:
            output_path = self.filepath
        
        try:
            # Hacer una copia del blob original
            modified_blob = bytearray(self.blob)
            
            # Actualizar cada parte
            for part_idx, part_info in enumerate(parts_data):
                if part_idx >= len(self.parts):
                    continue
                
                part_data_bytes = self.get_part_data(part_idx)
                if not part_data_bytes or len(part_data_bytes) < 4:
                    continue
                
                # Crear bytearray de la parte para modificar
                part_data = bytearray(part_data_bytes)
                
                # Procesar cada subparte
                for subpart in part_info['subparts']:
                    vertices = subpart['vertices']
                    vertex_count = subpart['vertex_count']
                    bone_count = subpart['bone_count']
                    subpart_offset = subpart['offset']
                    
                    weight_size = bone_count * 2
                    vertex_size = weight_size + 2 + 6
                    
                    # Escribir cada vértice
                    for v_idx, vertex in enumerate(vertices):
                        if v_idx >= vertex_count:
                            break
                        
                        vertex_offset = subpart_offset + (v_idx * vertex_size)
                        if vertex_offset + vertex_size > len(part_data):
                            break
                        
                        uv_offset = vertex_offset + weight_size
                        
                        # Escribir coordenadas UV (x, y) como bytes
                        uv_x = max(0, min(255, int(vertex['x'])))
                        uv_y = max(0, min(255, int(vertex['y'])))
                        
                        part_data[uv_offset] = uv_x
                        part_data[uv_offset + 1] = uv_y
                
                # Escribir la parte modificada de vuelta al blob
                part = self.parts[part_idx]
                modified_blob[part['offset']:part['end']] = part_data
            
            # Escribir el archivo modificado
            with open(output_path, 'wb') as f:
                f.write(modified_blob)
            
            print(f"[OK] PMDL guardado correctamente en: {output_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error al guardar PMDL: {e}")
            return False