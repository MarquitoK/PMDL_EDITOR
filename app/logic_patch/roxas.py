import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
import struct
import os
from PIL import Image, ImageTk
import sys
import io

class DBZCharacterAnalyzer:
    def __init__(self):
        self.file_path = None
        self.file_data = None
        self.pmdl_info = None
        self.texture_info = None
        
    def load_file(self, file_path):
        """Carga el archivo del personaje"""
        try:
            with open(file_path, 'rb') as f:
                self.file_data = bytearray(f.read())
            self.file_path = file_path
            print(f"\n{'='*60}")
            print(f"Archivo cargado: {os.path.basename(file_path)}")
            print(f"Tamaño: {len(self.file_data)} bytes (0x{len(self.file_data):X})")
            print(f"{'='*60}\n")
            
            # Validar y corregir el índice antes de continuar
            self.validate_and_fix_index()
            
            return True
        except Exception as e:
            print(f"Error al cargar archivo: {e}")
            return False
    
    def validate_and_fix_index(self):
        """
        Valida que el índice del personaje termine correctamente en 0x7CC
        Si los bytes 0x7CC-0x7CF no son 00 00 00 00, los corrige
        """
        print("Validando índice del personaje...")
        
        # El índice debe terminar en 0x7CC (los últimos 4 bytes deben ser 00)
        if len(self.file_data) < 0x7D0:
            print("⚠ Advertencia: Archivo muy pequeño para validar índice")
            return
        
        # Leer bytes 0x7CC - 0x7CF
        bytes_7cc = self.file_data[0x7CC:0x7D0]
        
        if bytes_7cc != b'\x00\x00\x00\x00':
            print(f"⚠ Índice incorrecto detectado en 0x7CC-0x7CF")
            print(f"  Valor actual: {bytes_7cc.hex().upper()}")
            print(f"  Corrigiendo a: 00 00 00 00")
            
            # Corregir los bytes
            self.file_data[0x7CC] = 0x00
            self.file_data[0x7CD] = 0x00
            self.file_data[0x7CE] = 0x00
            self.file_data[0x7CF] = 0x00
            
            print(f"✓ Índice corregido")
        else:
            print(f"✓ Índice válido (0x7CC-0x7CF = 00 00 00 00)")
    
    def read_offset(self, position):
        """Lee un offset de 4 bytes (big-endian) desde la posición indicada"""
        if position + 3 < len(self.file_data):
            # Leer como big-endian (bytes en orden: MSB primero)
            return struct.unpack('>I', self.file_data[position:position+4])[0]
        return 0
    
    def write_offset(self, position, value):
        """Escribe un offset de 4 bytes (big-endian) en la posición indicada"""
        if position + 3 < len(self.file_data):
            self.file_data[position:position+4] = struct.pack('>I', value)
    
    def find_pmdl_and_texture(self):
        """
        Lee el índice al inicio del archivo para encontrar pMdl y textura
        - pMdl: offset 0xC (inicio) y 0x13 (fin)
        - Textura: offset 0x30 (inicio) y 0x37 (fin)
        """
        if not self.file_data:
            print("No hay datos cargados")
            return False
        
        if len(self.file_data) < 0x40:
            print("Archivo muy pequeño, no contiene índice completo")
            return False
        
        print("Leyendo índice del personaje...")
        print(f"{'='*60}")
        
        # Leer offsets del pMdl (0xC - 0x13)
        pmdl_start = self.read_offset(0x0C)
        pmdl_end = self.read_offset(0x10)  # 0x13 es el byte, pero leemos desde 0x10
        
        print(f"\n📦 pMdl detectado:")
        print(f"   Inicio: 0x{pmdl_start:X} ({pmdl_start} bytes)")
        print(f"   Fin:    0x{pmdl_end:X} ({pmdl_end} bytes)")
        print(f"   Tamaño: 0x{pmdl_end - pmdl_start:X} ({pmdl_end - pmdl_start} bytes)")
        
        # Verificar que el pMdl está dentro del archivo
        if pmdl_start >= len(self.file_data) or pmdl_end > len(self.file_data):
            print(f"   ❌ ERROR: pMdl fuera de rango del archivo")
            return False
        
        self.pmdl_info = {
            'start': pmdl_start,
            'end': pmdl_end,
            'size': pmdl_end - pmdl_start
        }
        
        # Leer offsets de la textura (0x30 - 0x37)
        texture_start = self.read_offset(0x30)
        texture_end = self.read_offset(0x34)  # 0x37 es el byte, pero leemos desde 0x34
        
        print(f"\n🎨 Textura detectada:")
        print(f"   Inicio: 0x{texture_start:X} ({texture_start} bytes)")
        print(f"   Fin:    0x{texture_end:X} ({texture_end} bytes)")
        print(f"   Tamaño total: 0x{texture_end - texture_start:X} ({texture_end - texture_start} bytes)")
        
        # Verificar que la textura está dentro del archivo
        if texture_start >= len(self.file_data) or texture_end > len(self.file_data):
            print(f"   ❌ ERROR: Textura fuera de rango del archivo")
            return False
        
        # La textura tiene un header de 0x80 bytes que se ignora
        texture_header_size = 0x80
        texture_indices_start = texture_start + texture_header_size
        texture_indices_size = 0x10000  # 65536 bytes (256x256)
        palette_size = 0x400            # 1024 bytes (256 colores RGBA)
        
        palette_start = texture_indices_start + texture_indices_size
        
        print(f"   Header: 0x80 bytes (ignorado)")
        print(f"   Índices en: 0x{texture_indices_start:X}")
        print(f"   Tamaño índices: 0x{texture_indices_size:X} (256x256)")
        print(f"   Paleta en: 0x{palette_start:X}")
        print(f"   Tamaño paleta: 0x{palette_size:X} (256 colores RGBA)")
        
        # Verificar que tenemos espacio suficiente
        if palette_start + palette_size > len(self.file_data):
            print(f"   ❌ ERROR: No hay suficiente espacio para la textura completa")
            return False
        
        self.texture_info = {
            'start': texture_start,
            'end': texture_end,
            'header_size': texture_header_size,
            'indices_offset': texture_indices_start,
            'indices_size': texture_indices_size,
            'palette_offset': palette_start,
            'palette_size': palette_size,
            'width': 256,
            'height': 256
        }
        
        print(f"\n{'='*60}")
        print("✅ pMdl y textura identificados correctamente")
        print(f"{'='*60}\n")
        
        return True
    
    def generate_texture_image(self):
        """
        Genera la imagen de la textura usando el algoritmo exacto del C# ShowTex()
        Réplica 1:1 de las líneas 430-470 de Form1.cs
        """
        if not self.texture_info:
            print("No hay información de textura cargada")
            return None
        
        texture_offset = self.texture_info['indices_offset']
        palette_offset = self.texture_info['palette_offset']
        
        print(f"{'='*60}")
        print("GENERANDO IMAGEN DE TEXTURA")
        print(f"{'='*60}")
        print(f"Algoritmo: ShowTex() del código C# original")
        print(f"Leyendo desde offset 0x{texture_offset:X}")
        
        # Crear imagen RGB de 256x256 (Bitmap bitmap = new Bitmap(256, 256);)
        img = Image.new('RGB', (256, 256))
        pixels = img.load()
        
        # Leer paleta de colores (256 colores RGBA)
        print(f"\nCargando paleta desde 0x{palette_offset:X}...")
        palette = []
        for i in range(256):
            pal_offset = palette_offset + (i * 4)
            if pal_offset + 3 < len(self.file_data):
                r = self.file_data[pal_offset]
                g = self.file_data[pal_offset + 1]
                b = self.file_data[pal_offset + 2]
                # a = self.file_data[pal_offset + 3]  # Alpha ignorado en RGB
                palette.append((r, g, b))
            else:
                palette.append((0, 0, 0))
        
        print(f"✓ Paleta cargada: {len(palette)} colores")
        print(f"\nAplicando algoritmo de desentrelazado (bloques 16x8)...")
        
        # Variables exactas del código C# ShowTex()
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
        
        print(f"✓ Procesamiento completado")
        print(f"  Píxeles procesados: {num3}")
        print(f"  Dimensiones: 256x256")
        print(f"{'='*60}\n")
        
        return img
    
    def export_texture(self, output_path):
        """Exporta la textura a un archivo PNG"""
        if not self.texture_info:
            return False
        
        try:
            img = self.generate_texture_image()
            if img:
                img.save(output_path, 'PNG')
                print(f"✅ Textura exportada a: {output_path}")
                return True
        except Exception as e:
            print(f"❌ Error al exportar textura: {e}")
        return False
    
    def import_texture(self, input_path):
        """
        Importa una textura PNG y la convierte al formato del juego
        Réplica del método ReadTex() del C# original (líneas 490-550)
        """
        if not self.texture_info:
            print("❌ No hay información de textura cargada")
            return False
        
        try:
            print(f"\n{'='*60}")
            print(f"IMPORTANDO TEXTURA")
            print(f"{'='*60}")
            print(f"Archivo: {os.path.basename(input_path)}")
            
            # Cargar imagen
            img = Image.open(input_path)
            
            # Verificar dimensiones
            if img.size != (256, 256):
                print(f"❌ Error: La imagen debe ser 256x256 píxeles")
                print(f"   Tamaño actual: {img.width}x{img.height}")
                return False
            
            # Verificar que sea indexada (modo P) o convertir a indexada
            if img.mode != 'P':
                print(f"⚠ Imagen no indexada (modo {img.mode}), convirtiendo...")
                # Convertir a RGB primero si es necesario
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Convertir a indexada con 256 colores
                img = img.convert('P', palette=Image.ADAPTIVE, colors=256)
                print(f"✓ Convertida a modo indexado")
            
            # Verificar número de colores
            if img.mode == 'P':
                palette = img.getpalette()
                num_colors = len([i for i in range(0, len(palette), 3) if i < 768])
                if num_colors > 256:
                    print(f"❌ Error: La imagen tiene más de 256 colores ({num_colors})")
                    return False
                print(f"✓ Colores válidos: {num_colors}/256")
            
            print(f"\nProcesando textura...")
            
            texture_offset = self.texture_info['indices_offset']
            palette_offset = self.texture_info['palette_offset']
            
            # Algoritmo ReadTex() del C# original
            # Paso 1: Construir paleta desde la imagen
            print(f"Construyendo paleta...")
            
            palette_data = img.getpalette()
            num = 1  # Número de colores únicos (empieza en 1)
            
            # Limpiar área de paleta
            for i in range(256):
                pal_offset = palette_offset + (i * 4)
                if pal_offset + 3 < len(self.file_data):
                    self.file_data[pal_offset] = 0
                    self.file_data[pal_offset + 1] = 0
                    self.file_data[pal_offset + 2] = 0
                    self.file_data[pal_offset + 3] = 0
            
            # Construir mapeo de colores RGB a índices de paleta
            color_to_index = {}
            
            pixels = img.load()
            
            # Recorrer imagen para construir paleta única
            for y in range(256):
                for x in range(256):
                    pixel_index = pixels[x, y]
                    
                    # Obtener color RGB
                    r = palette_data[pixel_index * 3]
                    g = palette_data[pixel_index * 3 + 1]
                    b = palette_data[pixel_index * 3 + 2]
                    
                    color_key = (r, g, b)
                    
                    if color_key not in color_to_index:
                        # Buscar si el color ya existe en la paleta
                        found = False
                        for i in range(num):
                            pal_offset = palette_offset + (i * 4)
                            if (self.file_data[pal_offset] == r and 
                                self.file_data[pal_offset + 1] == g and 
                                self.file_data[pal_offset + 2] == b):
                                color_to_index[color_key] = i
                                found = True
                                break
                        
                        if not found:
                            # Agregar nuevo color a la paleta
                            if num < 256:
                                pal_offset = palette_offset + (num * 4)
                                self.file_data[pal_offset] = r
                                self.file_data[pal_offset + 1] = g
                                self.file_data[pal_offset + 2] = b
                                self.file_data[pal_offset + 3] = 255  # Alpha
                                color_to_index[color_key] = num
                                num += 1
            
            print(f"✓ Paleta construida: {num} colores únicos")
            
            # Paso 2: Escribir índices usando el algoritmo inverso del ShowTex()
            print(f"Escribiendo índices de textura...")
            
            num_x = 0    # x offset
            num_y = 0    # y offset
            num_idx = 0  # texture data index
            num4 = 32    # Outer loop
            
            while num4 != 0:
                num5 = 16  # Middle loop
                
                while num5 != 0:
                    num6 = 0  # Inner y
                    
                    while num6 < 8:
                        num7 = 0  # Inner x
                        
                        while num7 < 16:
                            if num_idx < 65536:
                                x = int(num7 + num_x)
                                y = int(num6 + num_y)
                                
                                if x < 256 and y < 256:
                                    pixel_index = pixels[x, y]
                                    r = palette_data[pixel_index * 3]
                                    g = palette_data[pixel_index * 3 + 1]
                                    b = palette_data[pixel_index * 3 + 2]
                                    
                                    color_key = (r, g, b)
                                    
                                    if color_key in color_to_index:
                                        idx = texture_offset + num_idx
                                        if idx < len(self.file_data):
                                            self.file_data[idx] = color_to_index[color_key]
                                
                                num_idx += 1
                            
                            num7 += 1
                        
                        num6 += 1
                    
                    if num_x + 2 < 256:
                        num_x += 16
                    
                    num5 -= 1
                
                if num_y + 2 < 256:
                    num_y += 8
                
                num_x = 0
                num4 -= 1
            
            print(f"✓ Índices escritos: {num_idx} píxeles")
            print(f"{'='*60}\n")
            print(f"✅ Textura importada exitosamente")
            
            return True
            
        except Exception as e:
            print(f"❌ Error al importar textura: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def export_pmdl(self, output_path):
        """Exporta el pMdl a un archivo .pmdl"""
        if not self.pmdl_info:
            return False
        
        try:
            start = self.pmdl_info['start']
            end = self.pmdl_info['end']
            
            with open(output_path, 'wb') as f:
                f.write(self.file_data[start:end])
            
            print(f"✅ pMdl exportado a: {output_path}")
            print(f"   Tamaño: {end - start} bytes (0x{end - start:X})")
            return True
            
        except Exception as e:
            print(f"❌ Error al exportar pMdl: {e}")
            return False
    
    def import_pmdl(self, input_path):
        """
        Importa un pMdl desde un archivo .pmdl
        Ajusta dinámicamente el tamaño del archivo y actualiza todos los offsets del índice
        Retorna información sobre el tipo de importación realizada
        """
        if not self.pmdl_info:
            print("❌ No hay información de pMdl cargada")
            return None
        
        try:
            print(f"\n{'='*60}")
            print(f"IMPORTANDO pMdl CON AJUSTE DINÁMICO")
            print(f"{'='*60}")
            
            # Leer archivo pMdl
            with open(input_path, 'rb') as f:
                new_pmdl_data = f.read()
            
            new_size = len(new_pmdl_data)
            old_size = self.pmdl_info['size']
            old_start = self.pmdl_info['start']
            old_end = self.pmdl_info['end']
            
            print(f"Archivo: {os.path.basename(input_path)}")
            print(f"Tamaño nuevo: {new_size} bytes (0x{new_size:X})")
            print(f"Tamaño original: {old_size} bytes (0x{old_size:X})")
            
            # Calcular diferencia
            size_diff = new_size - old_size
            import_type = "igual"  # "igual", "expandido", "reducido"
            
            if size_diff == 0:
                # Tamaño igual - reemplazo directo (método original)
                print(f"\n✓ Tamaño idéntico - Reemplazo directo")
                for i, byte in enumerate(new_pmdl_data):
                    self.file_data[old_start + i] = byte
                
                print(f"✓ pMdl reemplazado en offset 0x{old_start:X}")
                import_type = "igual"
                
            elif size_diff > 0:
                # pMdl más grande - expandir archivo
                print(f"\n⚠ pMdl más grande - Expandiendo archivo")
                print(f"  Diferencia: +{size_diff} bytes (+0x{size_diff:X})")
                
                # Crear nuevo bytearray con el tamaño expandido
                new_file_data = bytearray(len(self.file_data) + size_diff)
                
                # Copiar datos antes del pMdl
                new_file_data[0:old_start] = self.file_data[0:old_start]
                
                # Insertar nuevo pMdl
                new_file_data[old_start:old_start + new_size] = new_pmdl_data
                
                # Copiar datos después del pMdl (desplazados)
                new_file_data[old_start + new_size:] = self.file_data[old_end:]
                
                # Actualizar file_data
                self.file_data = new_file_data
                
                print(f"✓ Archivo expandido de {len(self.file_data) - size_diff} a {len(self.file_data)} bytes")
                
                # Actualizar todos los offsets del índice (0x10 hasta 0x7CB)
                print(f"\nActualizando offsets del índice...")
                self._update_index_offsets(old_end, size_diff)
                import_type = "expandido"
                
            else:  # size_diff < 0
                # pMdl más pequeño - reducir archivo
                print(f"\n⚠ pMdl más pequeño - Reduciendo archivo")
                print(f"  Diferencia: {size_diff} bytes (0x{size_diff:X})")
                
                bytes_to_remove = abs(size_diff)
                
                # Crear nuevo bytearray con el tamaño reducido
                new_file_data = bytearray(len(self.file_data) - bytes_to_remove)
                
                # Copiar datos antes del pMdl
                new_file_data[0:old_start] = self.file_data[0:old_start]
                
                # Insertar nuevo pMdl
                new_file_data[old_start:old_start + new_size] = new_pmdl_data
                
                # Copiar datos después del pMdl (desplazados hacia atrás)
                new_file_data[old_start + new_size:] = self.file_data[old_end:]
                
                # Actualizar file_data
                self.file_data = new_file_data
                
                print(f"✓ Archivo reducido de {len(self.file_data) + bytes_to_remove} a {len(self.file_data)} bytes")
                
                # Actualizar todos los offsets del índice (0x10 hasta 0x7CB)
                print(f"\nActualizando offsets del índice...")
                self._update_index_offsets(old_end, size_diff)
                import_type = "reducido"
            
            # Actualizar información del pMdl
            self.pmdl_info['end'] = old_start + new_size
            self.pmdl_info['size'] = new_size
            
            print(f"\n✓ Nuevo pMdl:")
            print(f"  Inicio: 0x{old_start:X}")
            print(f"  Fin: 0x{self.pmdl_info['end']:X}")
            print(f"  Tamaño: 0x{new_size:X}")
            
            print(f"\n{'='*60}")
            print(f"✅ pMdl importado y archivo ajustado exitosamente")
            print(f"{'='*60}\n")
            
            # Retornar información del resultado
            return {
                'type': import_type,
                'size_diff': size_diff,
                'old_size': old_size,
                'new_size': new_size
            }
            
        except Exception as e:
            print(f"❌ Error al importar pMdl: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _update_index_offsets(self, old_pmdl_end, size_diff):
        """
        Actualiza todos los offsets del índice después del pMdl
        Desde 0x10 (fin del pMdl) hasta 0x7CB (fin del índice)
        """
        # Los offsets en el índice están en posiciones específicas cada 4 bytes
        # Desde 0x10 hasta 0x7CB (el índice completo mide 0x7CC)
        
        updated_count = 0
        
        # Recorrer el índice de 4 en 4 bytes (cada offset)
        for offset_pos in range(0x10, 0x7CC, 4):
            # Leer el offset actual
            current_offset = self.read_offset(offset_pos)
            
            # Si el offset apunta a una posición después del pMdl original, ajustarlo
            if current_offset >= old_pmdl_end and current_offset > 0:
                new_offset = current_offset + size_diff
                
                # Escribir el nuevo offset
                self.write_offset(offset_pos, new_offset)
                
                print(f"  Offset en 0x{offset_pos:X}: 0x{current_offset:X} → 0x{new_offset:X}")
                updated_count += 1
        
        print(f"\n✓ {updated_count} offset(s) actualizados en el índice")
        
        # También actualizar la información de textura si existe
        if self.texture_info:
            old_tex_start = self.texture_info['start']
            if old_tex_start >= old_pmdl_end:
                print(f"\nActualizando información de textura...")
                
                self.texture_info['start'] += size_diff
                self.texture_info['end'] += size_diff
                self.texture_info['indices_offset'] += size_diff
                self.texture_info['palette_offset'] += size_diff
                
                print(f"✓ Textura desplazada a 0x{self.texture_info['start']:X}")
    
    def save_file(self, output_path=None):
        """Guarda el archivo modificado"""
        if not self.file_data:
            return False
        
        try:
            save_path = output_path if output_path else self.file_path
            
            with open(save_path, 'wb') as f:
                f.write(self.file_data)
            
            print(f"✅ Archivo guardado: {save_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error al guardar archivo: {e}")
            return False


class DBZApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("DBZ TTT Character Editor")
        self.geometry("700x600")
        self.minsize(600, 500)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.analyzer = DBZCharacterAnalyzer()
        self.texture_image = None
        self.current_ctk_image = None
        
        # Redireccionar prints a buffer interno
        self.console_buffer = io.StringIO()
        sys.stdout = ConsoleRedirector(self.console_buffer)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz mejorada"""
        # Configurar grid weights para responsividad
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Frame principal con padding
        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # ===== HEADER =====
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 20))
        
        title = ctk.CTkLabel(
            header_frame, 
            text="🐉 DBZ TTT Character Editor",
            font=("Arial", 28, "bold"),
            text_color=("#DB4437", "#DB4437")
        )
        title.pack()
        
        subtitle = ctk.CTkLabel(
            header_frame,
            text="Edita modelos y texturas de personajes",
            font=("Arial", 12),
            text_color=("gray60", "gray40")
        )
        subtitle.pack(pady=(5, 0))
        
        # ===== BOTÓN DE CARGA =====
        load_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        load_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 20))
        
        self.load_btn = ctk.CTkButton(
            load_frame,
            text="📁 Cargar Personaje",
            command=self.load_character,
            height=45,
            font=("Arial", 15, "bold"),
            corner_radius=10,
            fg_color=("#2196F3", "#1976D2"),
            hover_color=("#1976D2", "#1565C0")
        )
        self.load_btn.pack(fill="x")
        
        # ===== ÁREA DE TEXTURA =====
        texture_container = ctk.CTkFrame(main_frame, corner_radius=15)
        texture_container.grid(row=2, column=0, sticky="nsew", padx=30, pady=(0, 20))
        texture_container.grid_rowconfigure(1, weight=1)
        texture_container.grid_columnconfigure(0, weight=1)
        
        # Header de textura
        tex_header = ctk.CTkFrame(texture_container, fg_color="transparent", height=40)
        tex_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        
        tex_title = ctk.CTkLabel(
            tex_header,
            text="🎨 Textura del Personaje",
            font=("Arial", 16, "bold")
        )
        tex_title.pack(side="left")
        
        self.texture_info_label = ctk.CTkLabel(
            tex_header,
            text="",
            font=("Arial", 11),
            text_color=("gray50", "gray50")
        )
        self.texture_info_label.pack(side="right")
        
        # Frame para la imagen (centrado y responsive)
        self.texture_frame = ctk.CTkFrame(texture_container, fg_color="transparent")
        self.texture_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
        self.texture_frame.grid_rowconfigure(0, weight=1)
        self.texture_frame.grid_columnconfigure(0, weight=1)
        
        # Label para mostrar textura
        self.texture_label = ctk.CTkLabel(
            self.texture_frame,
            text="No hay textura cargada\n\nCarga un personaje para comenzar",
            font=("Arial", 13),
            text_color=("gray50", "gray50")
        )
        self.texture_label.grid(row=0, column=0)
        
        # Menú contextual para la textura
        self.texture_menu = Menu(self, tearoff=0, font=("Arial", 16))
        self.texture_menu.add_command(
            label="📤 Exportar Textura (PNG)", 
            command=self.export_texture_dialog
        )
        self.texture_menu.add_command(
            label="📥 Importar Textura (PNG)", 
            command=self.import_texture_dialog
        )
        
        self.texture_label.bind("<Button-3>", self.show_texture_menu)
        
        # ===== BOTONES DE ACCIÓN =====
        actions_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        actions_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 30))
        actions_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.export_pmdl_btn = ctk.CTkButton(
            actions_frame,
            text="📤 Exportar pMdl",
            command=self.export_pmdl_dialog,
            height=40,
            font=("Arial", 13, "bold"),
            state="disabled",
            corner_radius=8,
            fg_color=("#757575", "#616161"),
            hover_color=("#616161", "#424242")
        )
        self.export_pmdl_btn.grid(row=0, column=0, padx=5, sticky="ew")
        
        self.import_pmdl_btn = ctk.CTkButton(
            actions_frame,
            text="📥 Importar pMdl",
            command=self.import_pmdl_dialog,
            height=40,
            font=("Arial", 13, "bold"),
            state="disabled",
            corner_radius=8,
            fg_color=("#757575", "#616161"),
            hover_color=("#616161", "#424242")
        )
        self.import_pmdl_btn.grid(row=0, column=1, padx=5, sticky="ew")
        
        self.save_btn = ctk.CTkButton(
            actions_frame,
            text="💾 Guardar",
            command=self.save_character,
            height=40,
            font=("Arial", 13, "bold"),
            state="disabled",
            corner_radius=8,
            fg_color=("#4CAF50", "#388E3C"),
            hover_color=("#388E3C", "#2E7D32")
        )
        self.save_btn.grid(row=0, column=2, padx=5, sticky="ew")
        
        self.save_as_btn = ctk.CTkButton(
            actions_frame,
            text="💾 Guardar Como",
            command=self.save_character_as,
            height=40,
            font=("Arial", 13, "bold"),
            state="disabled",
            corner_radius=8,
            fg_color=("#4CAF50", "#388E3C"),
            hover_color=("#388E3C", "#2E7D32")
        )
        self.save_as_btn.grid(row=0, column=3, padx=5, sticky="ew")
    
    def load_character(self):
        """Carga y analiza un archivo de personaje"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo de personaje",
            filetypes=[
                ("Archivos PCK1", "*.PCK1"),
                ("Archivos PAK", "*.pak"),
                ("Todos los archivos", "*.*")
            ]
        )
        
        if file_path:
            # Limpiar buffer
            self.console_buffer.truncate(0)
            self.console_buffer.seek(0)
            
            self.texture_image = None
            
            # Mostrar indicador de carga
            self.load_btn.configure(state="disabled", text="⏳ Cargando...")
            self.update()
            
            try:
                if self.analyzer.load_file(file_path):
                    # Buscar pMdl y textura usando el índice
                    if self.analyzer.find_pmdl_and_texture():
                        # Generar imagen de textura
                        img = self.analyzer.generate_texture_image()
                        
                        if img:
                            self.texture_image = img
                            self.display_texture()
                            self.export_pmdl_btn.configure(state="normal")
                            self.import_pmdl_btn.configure(state="normal")
                            self.save_btn.configure(state="normal")
                            self.save_as_btn.configure(state="normal")
                            
                            # Actualizar info
                            filename = os.path.basename(file_path)
                            self.texture_info_label.configure(text=f"📄 {filename}")
                            
                            messagebox.showinfo(
                                "Éxito",
                                f"Personaje cargado correctamente\n\n"
                                f"Archivo: {filename}\n"
                                f"Tamaño: {len(self.analyzer.file_data):,} bytes"
                            )
                        else:
                            self.texture_label.configure(text="Error al generar textura")
                            messagebox.showerror("Error", "No se pudo generar la imagen de textura")
                    else:
                        self.texture_label.configure(text="No se pudo leer el índice del personaje")
                        messagebox.showerror("Error", "No se pudo leer el índice del archivo")
                else:
                    messagebox.showerror("Error", "No se pudo cargar el archivo")
            finally:
                self.load_btn.configure(state="normal", text="📁 Cargar Personaje")
    
    def display_texture(self):
        """Muestra la textura en la interfaz usando CTkImage"""
        if not self.texture_image:
            return
        
        # Calcular tamaño de visualización responsive
        container_width = self.texture_frame.winfo_width()
        container_height = self.texture_frame.winfo_height()
        
        # Usar un tamaño por defecto si el widget aún no se ha renderizado
        if container_width <= 1 or container_height <= 1:
            display_size = 350
        else:
            # Dejar margen de 40px
            max_size = min(container_width - 40, container_height - 40)
            display_size = max(200, min(max_size, 400))
        
        # Crear CTkImage (soporta HiDPI)
        self.current_ctk_image = ctk.CTkImage(
            light_image=self.texture_image,
            dark_image=self.texture_image,
            size=(display_size, display_size)
        )
        
        # Actualizar label
        self.texture_label.configure(image=self.current_ctk_image, text="")
    
    def show_texture_menu(self, event):
        """Muestra el menú contextual al hacer clic derecho en la textura"""
        if self.texture_image:
            try:
                self.texture_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.texture_menu.grab_release()
    
    def export_texture_dialog(self):
        """Diálogo para exportar la textura"""
        if not self.analyzer.texture_info:
            messagebox.showwarning("Advertencia", "No hay textura cargada")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Exportar Textura",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            if self.analyzer.export_texture(file_path):
                messagebox.showinfo("Éxito", f"Textura exportada correctamente a:\n{os.path.basename(file_path)}")
    
    def import_texture_dialog(self):
        """Diálogo para importar una textura"""
        if not self.analyzer.texture_info:
            messagebox.showwarning("Advertencia", "No hay textura cargada")
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar Textura (256x256, 256 colores)",
            filetypes=[("PNG Image", "*.png"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            if self.analyzer.import_texture(file_path):
                # Regenerar y mostrar la nueva textura
                img = self.analyzer.generate_texture_image()
                if img:
                    self.texture_image = img
                    self.display_texture()
                    messagebox.showinfo(
                        "Éxito", 
                        "Textura importada correctamente\n\n⚠ No olvides guardar los cambios"
                    )
            else:
                messagebox.showerror(
                    "Error", 
                    "No se pudo importar la textura\n\n"
                    "Verifica que:\n"
                    "• Sea una imagen de 256x256 píxeles\n"
                    "• Tenga 256 colores o menos"
                )
    
    def export_pmdl_dialog(self):
        """Diálogo para exportar el pMdl"""
        if not self.analyzer.pmdl_info:
            messagebox.showwarning("Advertencia", "No hay pMdl cargado")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Exportar pMdl",
            defaultextension=".pmdl",
            filetypes=[("pMdl File", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            if self.analyzer.export_pmdl(file_path):
                size = self.analyzer.pmdl_info['size']
                messagebox.showinfo(
                    "Éxito", 
                    f"pMdl exportado correctamente\n\n"
                    f"Archivo: {os.path.basename(file_path)}\n"
                    f"Tamaño: {size:,} bytes (0x{size:X})"
                )
    
    def import_pmdl_dialog(self):
        """Diálogo para importar un pMdl"""
        if not self.analyzer.pmdl_info:
            messagebox.showwarning("Advertencia", "No hay pMdl cargado")
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar pMdl",
            filetypes=[("pMdl File", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        
        if file_path:
            result = self.analyzer.import_pmdl(file_path)
            
            if result:
                # Construir mensaje según el tipo de importación
                if result['type'] == 'igual':
                    message = (
                        "pMdl importado correctamente\n\n"
                        "📏 Modelo del mismo tamaño\n"
                        f"Tamaño: {result['new_size']:,} bytes\n\n"
                        "⚠ No olvides guardar los cambios"
                    )
                elif result['type'] == 'expandido':
                    message = (
                        "pMdl importado correctamente\n\n"
                        "📈 Archivo expandido\n"
                        f"Tamaño original: {result['old_size']:,} bytes\n"
                        f"Tamaño nuevo: {result['new_size']:,} bytes\n"
                        f"✅ Sumado: +{result['size_diff']:,} bytes\n\n"
                        "⚠ No olvides guardar los cambios"
                    )
                else:  # reducido
                    message = (
                        "pMdl importado correctamente\n\n"
                        "📉 Archivo reducido\n"
                        f"Tamaño original: {result['old_size']:,} bytes\n"
                        f"Tamaño nuevo: {result['new_size']:,} bytes\n"
                        f"✅ Restado: {result['size_diff']:,} bytes\n\n"
                        "⚠ No olvides guardar los cambios"
                    )
                
                messagebox.showinfo("Éxito", message)
            else:
                messagebox.showerror("Error", "No se pudo importar el pMdl")
    
    def save_character(self):
        """Guarda los cambios directamente en el archivo original"""
        if not self.analyzer.file_data:
            return
        
        if self.analyzer.save_file():
            messagebox.showinfo("Éxito", "✅ Cambios guardados correctamente")
        else:
            messagebox.showerror("Error", "No se pudo guardar el archivo")
    
    def save_character_as(self):
        """Guarda los cambios como un nuevo archivo"""
        if not self.analyzer.file_data:
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Guardar Como",
            defaultextension=os.path.splitext(self.analyzer.file_path)[1],
            filetypes=[
                ("Archivos PCK1", "*.PCK1"),
                ("Archivos PAK", "*.pak"),
                ("Todos los archivos", "*.*")
            ]
        )
        
        if file_path:
            if self.analyzer.save_file(file_path):
                messagebox.showinfo("Éxito", f"✅ Archivo guardado como:\n{os.path.basename(file_path)}")
            else:
                messagebox.showerror("Error", "No se pudo guardar el archivo")


class ConsoleRedirector:
    """Redirige print() a un buffer interno (sin mostrar en UI)"""
    def __init__(self, buffer):
        self.buffer = buffer
    
    def write(self, text):
        self.buffer.write(text)
    
    def flush(self):
        pass


if __name__ == "__main__":
    app = DBZApp()
    app.mainloop()