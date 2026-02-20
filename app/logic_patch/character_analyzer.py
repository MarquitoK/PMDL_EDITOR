import struct
import os
from PIL import Image


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
        """
        Valida que el índice del personaje termine correctamente en 0x7CC.
        Si los bytes 0x7CC-0x7CF no son 00 00 00 00, los corrige.
        """
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
        """
        Lee el índice al inicio del archivo para encontrar pMdl y textura.
        - pMdl: offset 0xC (inicio) y 0x10 (fin)
        - Textura: offset 0x30 (inicio) y 0x34 (fin)
        """
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
            # La textura tiene un header de 0x80 bytes que se ignora
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
        """
        Actualiza el PMDL en el parche con nuevos datos.
        Ajusta dinámicamente el tamaño del archivo.
        """
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
        """
        Actualiza todos los offsets del índice que apuntan a datos después del pMdl.
        El índice va desde 0x10 hasta 0x7CB (pares de offsets cada 4 bytes).
        """
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
        
        texture_offset = self.texture_info['indices_offset']
        palette_offset = self.texture_info['palette_offset']
        
        # Crear imagen RGB de 256x256
        img = Image.new('RGB', (256, 256))
        pixels = img.load()
        
        # Leer paleta de colores
        palette = []
        for i in range(256):
            pal_offset = palette_offset + (i * 4)
            if pal_offset + 3 < len(self.file_data):
                r = self.file_data[pal_offset]
                g = self.file_data[pal_offset + 1]
                b = self.file_data[pal_offset + 2]
                # a = self.file_data[pal_offset + 3]
                palette.append((r, g, b))
            else:
                palette.append((0, 0, 0))
        
        num = 0      # uint num = 0u;
        num2 = 0     # uint num2 = 0u;
        num3 = 0     # uint num3 = 0u;
        num4 = 32    # uint num4 = 32u;
        
        # do { ... } while (num4 != 0);
        while num4 != 0:
            num5 = 16  # uint num5 = 16u;
            
            # do { ... } while (num5 != 0);
            while num5 != 0:
                num6 = 0  # uint num6 = 0u;
                
                # do { ... } while (num6 < 8);
                while num6 < 8:
                    num7 = 0  # uint num7 = 0u;
                    
                    # do { ... } while (num7 < 16);
                    while num7 < 16:
                        # if (num3 < 65536)
                        if num3 < 65536:
                            # Leer índice de paleta desde la textura
                            idx = texture_offset + num3
                            if idx < len(self.file_data):
                                color_index = self.file_data[idx]
                                
                                # Obtener color RGB de la paleta
                                if color_index < len(palette):
                                    color = palette[color_index]
                                else:
                                    color = (0, 0, 0)
                                
                                # bitmap.SetPixel((int)(num7 + num), (int)(num6 + num2), color);
                                x = int(num7 + num)
                                y = int(num6 + num2)
                                
                                if x < 256 and y < 256:
                                    pixels[x, y] = color
                            
                            # num3++;
                            num3 += 1
                        
                        # num7++;
                        num7 += 1
                    
                    # num6++;
                    num6 += 1
                
                # if (num + 2 < 256) { num += 16; }
                if num + 2 < 256:
                    num += 16
                
                # num5--;
                num5 -= 1
            
            # if (num2 + 2 < 256) { num2 += 8; }
            if num2 + 2 < 256:
                num2 += 8
            
            # num = 0u;
            num = 0
            
            # num4--;
            num4 -= 1
        
        return img
    
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
        """
        Importa una textura desde un archivo de imagen.
        Ajusta dinámicamente el tamaño del archivo.
        """
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
        face_definitions = [
            ("Cara de daño", 0x10, 0x14),
            ("Cara 1", 0x20, 0x24),
            ("Cara 2", 0x24, 0x28),
            ("Cara 3", 0x28, 0x2C),
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