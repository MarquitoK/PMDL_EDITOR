import struct
import os


class CharacterAnalyzer:
    """Analizador de archivos de personajes DBZ TTT."""
    
    def __init__(self):
        self.file_path = None
        self.file_data = None
        self.pmdl_info = None
        self.texture_info = None
        
    def load_file(self, file_path):
        """Carga el archivo del personaje."""
        try:
            with open(file_path, 'rb') as f:
                self.file_data = bytearray(f.read())
            self.file_path = file_path
            
            # Validar y corregir el índice antes de continuar
            self.validate_and_fix_index()
            return True
        except Exception as e:
            print(f"Error al cargar archivo: {e}")
            return False
    
    def validate_and_fix_index(self):
        if len(self.file_data) < 0x7D0:
            return
        
        bytes_7cc = self.file_data[0x7CC:0x7D0]
        
        if bytes_7cc != b'\x00\x00\x00\x00':
            # Corregir los bytes
            self.file_data[0x7CC:0x7D0] = b'\x00\x00\x00\x00'
    
    def read_offset(self, position):
        """Lee un offset de 4 bytes (big-endian) desde la posición indicada."""
        if position + 3 < len(self.file_data):
            return struct.unpack('>I', self.file_data[position:position+4])[0]
        return 0
    
    def write_offset(self, position, value):
        """Escribe un offset de 4 bytes (big-endian) en la posición indicada."""
        if position + 3 < len(self.file_data):
            self.file_data[position:position+4] = struct.pack('>I', value)
    
    def find_pmdl_and_texture(self):
        if not self.file_data or len(self.file_data) < 0x40:
            return False
        
        # Leer offsets del pMdl
        pmdl_start = self.read_offset(0x0C)
        pmdl_end = self.read_offset(0x10)
        
        if pmdl_start >= pmdl_end or pmdl_end > len(self.file_data):
            return False
        
        # Verificar firma pMdl o pMdF
        signature = self.file_data[pmdl_start:pmdl_start+4]
        if signature not in (b'pMdl', b'pMdF'):
            return False
        
        pmdl_size = pmdl_end - pmdl_start
        
        self.pmdl_info = {
            'start': pmdl_start,
            'end': pmdl_end,
            'size': pmdl_size
        }
        
        # Leer offsets de textura
        texture_start = self.read_offset(0x30)
        texture_end = self.read_offset(0x34)
        
        if texture_start < texture_end and texture_end <= len(self.file_data):
            texture_header_size = 0x80
            texture_indices_start = texture_start + texture_header_size
            texture_indices_size = 0x10000
            palette_size = 0x400
            
            palette_start = texture_indices_start + texture_indices_size
            
            # Verificar que tenemos espacio suficiente
            if palette_start + palette_size <= len(self.file_data):
                self.texture_info = {
                    'start': texture_start,
                    'end': texture_end,
                    'size': texture_end - texture_start,
                    'header_size': texture_header_size,
                    'indices_offset': texture_indices_start,
                    'indices_size': texture_indices_size,
                    'palette_offset': palette_start,
                    'palette_size': palette_size,
                    'width': 256,
                    'height': 256
                }
        
        return True
    
    def get_pmdl_data(self):
        """Obtiene los datos del PMDL como bytearray."""
        if not self.pmdl_info:
            return None
        
        start = self.pmdl_info['start']
        end = self.pmdl_info['end']
        return bytearray(self.file_data[start:end])
    
    def set_pmdl_data(self, pmdl_data):
        if not self.pmdl_info:
            return False
        
        try:
            new_size = len(pmdl_data)
            old_size = self.pmdl_info['size']
            old_start = self.pmdl_info['start']
            old_end = self.pmdl_info['end']
            
            size_diff = new_size - old_size
            
            if size_diff == 0:
                # Tamaño igual - reemplazo directo
                self.file_data[old_start:old_end] = pmdl_data
                
            elif size_diff > 0:
                # pMdl más grande - expandir archivo
                new_file_data = bytearray(len(self.file_data) + size_diff)
                
                # Copiar datos antes del pMdl
                new_file_data[0:old_start] = self.file_data[0:old_start]
                
                # Insertar nuevo pMdl
                new_file_data[old_start:old_start + new_size] = pmdl_data
                
                # Copiar datos después del pMdl
                new_file_data[old_start + new_size:] = self.file_data[old_end:]
                
                # Actualizar file_data
                self.file_data = new_file_data
                
                # Actualizar todos los offsets del índice
                self._update_index_offsets(old_end, size_diff)
                
            else:
                # pMdl más pequeño - reducir archivo
                new_file_data = bytearray(len(self.file_data) + size_diff)
                
                # Copiar datos antes del pMdl
                new_file_data[0:old_start] = self.file_data[0:old_start]
                
                # Insertar nuevo pMdl
                new_file_data[old_start:old_start + new_size] = pmdl_data
                
                # Copiar datos después del pMdl
                new_file_data[old_start + new_size:] = self.file_data[old_end:]
                
                # Actualizar file_data
                self.file_data = new_file_data
                
                # Actualizar todos los offsets del índice
                self._update_index_offsets(old_end, size_diff)
            
            # Actualizar información del pMdl
            self.pmdl_info['size'] = new_size
            self.pmdl_info['end'] = old_start + new_size
            
            # Actualizar offset del pMdl en el índice
            self.write_offset(0x10, self.pmdl_info['end'])
            
            return True
            
        except Exception as e:
            print(f"Error al actualizar PMDL: {e}")
            return False
    
    def _update_index_offsets(self, old_pmdl_end, size_diff):
        # Recorrer el índice de 0x10 a 0x7CB
        for offset_pos in range(0x10, 0x7CC, 4):
            current_offset = self.read_offset(offset_pos)
            
            # Si el offset apunta después del fin del pMdl original, ajustarlo
            if current_offset >= old_pmdl_end and current_offset != 0:
                new_offset = current_offset + size_diff
                self.write_offset(offset_pos, new_offset)
    
    def generate_texture_image(self):
        if not self.texture_info:
            return None
        
        try:
            from app.utils.atex_reader import atex_to_pil
            texture_start = self.texture_info['start']
            texture_end   = self.texture_info['end']
            return atex_to_pil(bytes(self.file_data[texture_start:texture_end]))
        except Exception as e:
            print(f"Error al generar imagen de textura: {e}")
            return None
    
    def export_texture(self, output_path):
        """Exporta la textura a un archivo de imagen."""
        img = self.generate_texture_image()
        if img:
            try:
                img.save(output_path)
                return True
            except Exception as e:
                print(f"Error al exportar textura: {e}")
                return False
        return False
    
    def get_texture_data(self):
        """Genera la textura y retorna los datos como bytes PNG."""
        img = self.generate_texture_image()
        if img:
            try:
                import io
                # Guardar imagen en memoria como PNG
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                return buffer.getvalue()
            except Exception as e:
                print(f"Error al generar datos de textura: {e}")
                return None
        return None
    
    def import_texture(self, input_path):
        if not self.texture_info:
            return False
        
        try:
            # Leer nueva textura
            with open(input_path, 'rb') as f:
                new_texture_data = f.read()
            
            new_size = len(new_texture_data)
            old_size = self.texture_info['size']
            old_start = self.texture_info['start']
            old_end = self.texture_info['end']
            
            size_diff = new_size - old_size
            
            if size_diff == 0:
                # Tamaño igual
                self.file_data[old_start:old_end] = new_texture_data
                
            elif size_diff > 0:
                # Expandir
                new_file_data = bytearray(len(self.file_data) + size_diff)
                new_file_data[0:old_start] = self.file_data[0:old_start]
                new_file_data[old_start:old_start + new_size] = new_texture_data
                new_file_data[old_start + new_size:] = self.file_data[old_end:]
                self.file_data = new_file_data
                self._update_texture_offsets(old_end, size_diff)
                
            else:
                # Reducir
                new_file_data = bytearray(len(self.file_data) + size_diff)
                new_file_data[0:old_start] = self.file_data[0:old_start]
                new_file_data[old_start:old_start + new_size] = new_texture_data
                new_file_data[old_start + new_size:] = self.file_data[old_end:]
                self.file_data = new_file_data
                self._update_texture_offsets(old_end, size_diff)
            
            # Actualizar información de textura
            self.texture_info['size'] = new_size
            self.texture_info['end'] = old_start + new_size
            
            # Actualizar offset de textura en el índice
            self.write_offset(0x34, self.texture_info['end'])
            
            return True
            
        except Exception as e:
            print(f"Error al importar textura: {e}")
            return False
    
    def import_texture_raw(self, raw_data: bytes) -> bool:
        if not self.texture_info:
            return False
        try:
            new_size  = len(raw_data)
            old_size  = self.texture_info['size']
            old_start = self.texture_info['start']
            old_end   = self.texture_info['end']
            size_diff = new_size - old_size

            if size_diff == 0:
                self.file_data[old_start:old_end] = raw_data
            else:
                new_file = bytearray(len(self.file_data) + size_diff)
                new_file[0:old_start] = self.file_data[0:old_start]
                new_file[old_start:old_start + new_size] = raw_data
                new_file[old_start + new_size:] = self.file_data[old_end:]
                self.file_data = new_file
                self._update_texture_offsets(old_end, size_diff)

            self.texture_info['size'] = new_size
            self.texture_info['end']  = old_start + new_size
            self.write_offset(0x34, self.texture_info['end'])
            return True
        except Exception as e:
            print(f"Error al importar textura RAW: {e}")
            return False

    def _update_texture_offsets(self, old_texture_end, size_diff):
        """Actualiza offsets que apuntan después de la textura."""
        for offset_pos in range(0x34, 0x7CC, 4):
            current_offset = self.read_offset(offset_pos)
            if current_offset >= old_texture_end and current_offset != 0:
                new_offset = current_offset + size_diff
                self.write_offset(offset_pos, new_offset)
    
    def export_pmdl(self, output_path):
        """Exporta el pMdl a un archivo .pmdl."""
        if not self.pmdl_info:
            return False
        
        try:
            start = self.pmdl_info['start']
            end = self.pmdl_info['end']
            
            with open(output_path, 'wb') as f:
                f.write(self.file_data[start:end])
            
            return True
            
        except Exception as e:
            print(f"Error al exportar pMdl: {e}")
            return False
    
    def import_pmdl(self, input_path):
        """Importa un pMdl desde un archivo .pmdl."""
        try:
            with open(input_path, 'rb') as f:
                new_pmdl_data = f.read()
            
            return self.set_pmdl_data(bytearray(new_pmdl_data))
            
        except Exception as e:
            print(f"Error al importar pMdl: {e}")
            return False
    
    def save_file(self, output_path=None):
        """Guarda el archivo del personaje."""
        if not self.file_data:
            return False
        
        path = output_path if output_path else self.file_path
        if not path:
            return False
        
        try:
            with open(path, 'wb') as f:
                f.write(self.file_data)
            
            if output_path:
                self.file_path = output_path
            
            return True
            
        except Exception as e:
            print(f"Error al guardar archivo: {e}")
            return False
    
    def find_extra_faces(self):
        #Lee el índice para encontrar caras extra (PMDFs).
        if not self.file_data or len(self.file_data) < 0x40:
            return {}
        
        faces = {}
        # CARAS_PMDF
        face_definitions = [
            ("Cara_damage",   0x10, 0x14),
            ("Cara_hablar_1", 0x14, 0x18),
            ("Cara_hablar_2", 0x18, 0x1C),
            ("Cara_hablar_3", 0x1C, 0x20),
            ("Cara_1",        0x20, 0x24),
            ("Cara_2",        0x24, 0x28),
            ("Cara_3",        0x28, 0x2C),
            ("Cara_no_usada", 0x2C, 0x30),
        ]
        
        for name, start_offset, end_offset in face_definitions:
            face_start = self.read_offset(start_offset)
            face_end = self.read_offset(end_offset)
            
            # Validar que el rango sea válido
            if face_start > 0 and face_end > face_start and face_end <= len(self.file_data):
                # Verificar firma pMdl o pMdF
                signature = self.file_data[face_start:face_start+4]
                if signature in (b'pMdl', b'pMdF'):
                    faces[name] = {
                        'start': face_start,
                        'end': face_end,
                        'size': face_end - face_start,
                        'start_offset_pos': start_offset,
                        'end_offset_pos': end_offset
                    }
        
        return faces
    
    def get_face_data(self, face_name):
        faces = self.find_extra_faces()
        if face_name not in faces:
            return None
        
        info = faces[face_name]
        return bytearray(self.file_data[info['start']:info['end']])
    
    def set_face_data(self, face_name, face_data):
        faces = self.find_extra_faces()
        if face_name not in faces:
            return False
        
        try:
            old_info = faces[face_name]
            old_start = old_info['start']
            old_end = old_info['end']
            old_size = old_info['size']
            new_size = len(face_data)
            
            # Reemplazar datos
            self.file_data[old_start:old_end] = face_data
            
            # Calcular delta
            delta = new_size - old_size
            
            if delta != 0:
                # Actualizar offset de fin en el índice
                self.write_offset(old_info['end_offset_pos'], old_end + delta)
                
                # Actualizar offsets de todo lo que viene después
                self._adjust_offsets_after(old_end, delta)
            
            return True
            
        except Exception as e:
            print(f"Error al actualizar cara extra: {e}")
            return False
    
    def _adjust_offsets_after(self, position, delta):
        # Recorrer todo el índice (hasta 0x7CC)
        for offset_pos in range(0, 0x7CC, 4):
            current_offset = self.read_offset(offset_pos)
            if current_offset > position:
                self.write_offset(offset_pos, current_offset + delta)
            return False