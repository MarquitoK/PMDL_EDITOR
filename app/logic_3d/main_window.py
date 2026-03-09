import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import colorsys
import tempfile
import os

from .pmdl_reader import analizar_pmdl
from .mesh_processor import merge_vertices_by_distance
from .gl_viewport import GLViewport
from app.logic_uvs.canvas import UVCanvas
from app.logic_uvs.parser import PmdlParser
from app.utils.icon import set_app_icon

ESCALA: float =  0.00051875

class PMDLViewerApp(ctk.CTkToplevel):
    def __init__(self, parent, pmdl_data=None, texture_path=None, is_secondary=False):
        super().__init__(parent)
        
        self.title("Vista 3D - PMDL Viewer" + (" (Secundario)" if is_secondary else ""))
        self.geometry("1280x720")
        
        set_app_icon(self)
        
        self.pmdl_data = None
        self.escala = ESCALA
        self.texture_loaded = False
        self.temp_pmdl_path = None
        self.temp_texture_path = texture_path
        # True solo si la app creó ese archivo temporal y debe borrarlo al cerrar
        # False si apunta a un archivo del usuario (PNG del escritorio, etc.)
        self._temp_texture_owned = False  # texture_path viene del editor — se gestiona allá
        self.has_unsaved_changes = False
        # 'inherited' = vino del editor principal | 'explicit' = abierto desde aquí
        self.pmdl_origin = 'inherited' if pmdl_data else None
        self.pmdl_explicit_path = None
        
        # Editor de UVs
        self.uv_editor_window = None
        self.is_secondary_pmdl = is_secondary 

        # Editor de UVs integrado
        self.uv_panel_visible = False
        self.uv_panel = None
        self.uv_canvas = None
        self.uv_parser = None
        self.parte_seleccionada = None
        
        # Bind para detectar inicio/fin de movimiento de ventana
        self.bind("<ButtonPress-1>", self._on_window_move_start, add="+")
        self.bind("<ButtonRelease-1>", self._on_window_move_end, add="+")
        
        self.setup_ui()
        
        # Bindings globales para Undo/Redo
        self.bind_all("<Control-z>", self._global_undo)
        self.bind_all("<Control-y>", self._global_redo)
        
        if pmdl_data:
            self.after(200, lambda: self._load_from_data(pmdl_data, texture_path))
    
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        
        # Grid: [Partes][3D][Splitter][Panel UV]
        self.grid_columnconfigure(0, weight=0, minsize=150)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=4)
        self.grid_columnconfigure(3, weight=0)
        self.grid_rowconfigure(1, weight=1)
        
        # BARRA SUPERIOR
        top_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        top_frame.grid(row=0, column=0, columnspan=4, sticky="ew", padx=0, pady=0)
        top_frame.grid_columnconfigure(1, weight=1)
        
        self.btn_cargar = ctk.CTkButton(
            top_frame, text="Abrir PMDL", 
            command=self.cargar_archivo,
            width=150, height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        # Solo mostrar en visor principal, no en secundario
        if not self.is_secondary_pmdl:
            self.btn_cargar.grid(row=0, column=0, padx=20, pady=10)
        
        # Frame para los labels de archivo y textura
        labels_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        labels_frame.grid(row=0, column=1, padx=20, sticky="w")
        
        self.lbl_archivo = ctk.CTkLabel(
            labels_frame, text="No hay archivo cargado",
            font=ctk.CTkFont(size=13),
            text_color=("gray60", "gray40")
        )
        self.lbl_archivo.pack(side="left", padx=(0, 15))
        
        self.lbl_textura = ctk.CTkLabel(
            labels_frame, text="",
            font=ctk.CTkFont(size=13),
            text_color=("gray60", "gray40")
        )
        self.lbl_textura.pack(side="left")
        
        # Frame para los 3 botones de modo de renderizado
        self.render_mode_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        self.render_mode_frame.grid(row=0, column=2, padx=10)
        
        self.btn_bones = ctk.CTkButton(
            self.render_mode_frame, text="Huesos",
            command=self.toggle_bones,
            width=80, height=35,
            font=ctk.CTkFont(size=11),
            fg_color=("#9C27B0", "#7B1FA2"),
            hover_color=("#7B1FA2", "#6A1B9A")
        )
        self.btn_bones.grid(row=0, column=0, padx=2)
        
        ctk.CTkLabel(self.render_mode_frame, text="", width=10).grid(row=0, column=1)
        
        self.btn_solid = ctk.CTkButton(
            self.render_mode_frame, text="Sólido",
            command=lambda: self.set_render_mode("solid"),
            width=80, height=35,
            font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray30")
        )
        self.btn_solid.grid(row=0, column=2, padx=2)
        
        self.btn_texture = ctk.CTkButton(
            self.render_mode_frame, text="Textura",
            command=lambda: self.set_render_mode("texture"),
            width=80, height=35,
            font=ctk.CTkFont(size=11),
            fg_color=("#3B8ED0", "#1F6AA5")
        )
        self.btn_texture.grid(row=0, column=3, padx=2)
        
        self.btn_wireframe = ctk.CTkButton(
            self.render_mode_frame, text="Wireframe",
            command=lambda: self.set_render_mode("wireframe"),
            width=80, height=35,
            font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray30")
        )
        self.btn_wireframe.grid(row=0, column=4, padx=2)
        
        self.current_render_mode = "texture"
        
        self.btn_textura = ctk.CTkButton(
            top_frame, text="Importar Textura",
            command=self.importar_textura,
            width=150, height=40,
            font=ctk.CTkFont(size=13),
            fg_color=("#28a745", "#1e7e34"),
            hover_color=("#218838", "#155724")
        )
        self.btn_textura.grid(row=0, column=3, padx=10)
        
        # Botón Editar UVs
        self.btn_edit_uvs = ctk.CTkButton(
            top_frame, text="✏️ Editar UVs",
            command=self.toggle_uv_panel,
            width=130, height=40,
            font=ctk.CTkFont(size=13),
            fg_color=("#FF8C00", "#FF6F00"),
            hover_color=("#FF7F00", "#FF5500"),
            state="disabled"
        )
        # Solo mostrar el botón si NO es secundario
        if not self.is_secondary_pmdl:
            self.btn_edit_uvs.grid(row=0, column=4, padx=10)
        
        # PANEL IZQUIERDO
        left_frame = ctk.CTkFrame(self, width=150, corner_radius=0)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 1), pady=0)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_propagate(False)
        left_frame.grid_columnconfigure(0, weight=1)
        
        lbl_titulo = ctk.CTkLabel(
            left_frame, text="Partes",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_titulo.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")
        
        list_container = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 15))
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        self.partes_frame = ctk.CTkScrollableFrame(
            list_container,
            width=240,
            fg_color=("gray85", "gray20")
        )
        self.partes_frame.grid(row=0, column=0, sticky="nsew")
        
        self.lbl_stats = ctk.CTkLabel(
            left_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray50")
        )
        self.lbl_stats.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="w")
        
        # PANEL DERECHO
        right_frame = ctk.CTkFrame(self, corner_radius=0)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        
        if GLViewport:
            self.gl_viewport = GLViewport(right_frame, width=800, height=600)
            self.gl_viewport.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
            
            # Widget de info con texto enriquecido
            # Widget de info con texto enriquecido (oculto hasta que haya selección)
            self.info_label = tk.Text(
                right_frame,
                bg="#1e1e1e", fg="white",
                font=("Segoe UI", 11),
                relief="flat", bd=0,
                highlightthickness=1,
                highlightbackground="#444",
                padx=10, pady=8,
                state="disabled",
                cursor="arrow",
                wrap="none",
                width=26, height=7
            )
            # NO se coloca con .place() aquí — se muestra dinámicamente
            self.info_label.tag_configure("bold_white",   font=("Segoe UI", 11, "bold"),   foreground="white")
            self.info_label.tag_configure("normal_white", font=("Segoe UI", 11),            foreground="white")
            self.info_label.tag_configure("yellow",       font=("Segoe UI", 11),            foreground="#FFD700")
            self.info_label.tag_configure("bold_yellow",  font=("Segoe UI", 11, "bold"),    foreground="#FFD700")
            self.info_label.tag_configure("light_gray",   font=("Segoe UI", 11),            foreground="#aaaaaa")
            self.gl_viewport.info_label = self.info_label
            self.gl_viewport.parent_app = self
            
            info_frame = ctk.CTkFrame(right_frame, height=50)
            info_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 15))
            
            self.lbl_controles = ctk.CTkLabel(
                info_frame,
                text="Scroll: Zoom • Rueda presionada: Rotar • Shift+Rueda: Mover • Click Der: Mover • Click Izq: Seleccionar • ç o /: Aislar",
                font=ctk.CTkFont(size=11),
                text_color=("gray40", "gray60")
            )
            self.lbl_controles.pack(pady=10)
        else:
            error_label = ctk.CTkLabel(
                right_frame,
                text="⚠️ PyOpenGL no instalado\npip install pyopengltk PyOpenGL",
                font=ctk.CTkFont(size=14),
                text_color="orange"
            )
            error_label.place(relx=0.5, rely=0.5, anchor="center")
    
    def set_render_mode(self, mode):
        """Cambia el modo de renderizado (solid, texture, wireframe)"""
        if not GLViewport or not hasattr(self, 'gl_viewport'):
            return
        
        self.current_render_mode = mode
        
        # Actualizar colores de botones
        if mode == "solid":
            self.btn_solid.configure(fg_color=("#3B8ED0", "#1F6AA5"))
            self.btn_texture.configure(fg_color=("gray75", "gray25"))
            self.btn_wireframe.configure(fg_color=("gray75", "gray25"))
        elif mode == "texture":
            self.btn_solid.configure(fg_color=("gray75", "gray25"))
            self.btn_texture.configure(fg_color=("#3B8ED0", "#1F6AA5"))
            self.btn_wireframe.configure(fg_color=("gray75", "gray25"))
        elif mode == "wireframe":
            self.btn_solid.configure(fg_color=("gray75", "gray25"))
            self.btn_texture.configure(fg_color=("gray75", "gray25"))
            self.btn_wireframe.configure(fg_color=("#3B8ED0", "#1F6AA5"))
        
        self.gl_viewport.set_render_mode(mode)
    
    def importar_textura(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar textura",
            filetypes=[
                ("Imágenes PNG", "*.png"),
                ("Texturas RAW", "*.atex *.unk"),
                ("Todas", "*.png *.atex *.unk *.jpg *.jpeg")
            ]
        )
        if not filepath:
            return

        ext = os.path.splitext(filepath)[1].lower()
        if ext in (".atex", ".unk"):
            try:
                import tempfile
                from app.utils.atex_reader import atex_to_pil
                with open(filepath, 'rb') as f:
                    raw = f.read()
                img = atex_to_pil(raw)
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp:
                    img.save(tmp.name)
                    png_path = tmp.name
                # Borrar el temporal previo si era nuestro
                if self._temp_texture_owned and self.temp_texture_path and os.path.exists(self.temp_texture_path):
                    try: os.unlink(self.temp_texture_path)
                    except: pass
                self.temp_texture_path = png_path
                self._temp_texture_owned = True  # este PNG lo creamos nosotros
                filepath = png_path
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer la textura RAW:\n{e}")
                return

        if GLViewport and hasattr(self, 'gl_viewport'):
            if self.gl_viewport.load_texture(filepath):
                # Guardar ruta para que el canvas UV pueda accederla después
                # Solo actualizar si no fue ya seteado por la rama RAW arriba
                if not (os.path.splitext(filepath)[1].lower() in (".atex", ".unk")):
                    # Es un PNG/imagen directa del usuario — NO es nuestro temporal
                    if self._temp_texture_owned and self.temp_texture_path and os.path.exists(self.temp_texture_path):
                        try: os.unlink(self.temp_texture_path)
                        except: pass
                    self.temp_texture_path = filepath
                    self._temp_texture_owned = False  # archivo del usuario, no tocar
                texture_name = os.path.basename(filepath)
                self.lbl_textura.configure(
                    text=f"🖼️ {texture_name}",
                    text_color=("green", "lightgreen")
                )
                if self.pmdl_data:
                    self.seleccionar_parte(-1)
                # Habilitar editor UVs si ya hay PMDL cargado
                if self.pmdl_data and not self.is_secondary_pmdl and hasattr(self, 'btn_edit_uvs'):
                    self.btn_edit_uvs.configure(state="normal")
                # Si el panel UV está abierto, actualizar textura en canvas
                if self.uv_panel_visible and self.uv_canvas:
                    self.uv_canvas.load_texture(filepath)
                    self.load_uvs_for_selected_part()
            else:
                messagebox.showerror("Error", "No se pudo cargar la textura")
    
    def cargar_archivo(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo PMDL/PMDF",
            filetypes=[
                ("Archivos PMDL", "*.pmdl"),
                ("Archivos PMDF", "*.pmdf"),
                ("Archivos Unknown", "*.unk"),
                ("Todos", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        info, error = analizar_pmdl(filepath)
        
        if error:
            messagebox.showerror("Error", error)
            return
        
        self.pmdl_data = info
        # Abierto explícitamente desde el visor — no hereda del editor principal
        self.pmdl_origin = 'explicit'
        self.pmdl_explicit_path = filepath
        self.temp_pmdl_path = filepath  # UV editor también necesita esta ruta
        self.lbl_archivo.configure(
            text=f"✅ {info['nombre']} ({info['tipo']})",
            text_color=("green", "lightgreen")
        )
        
        self.poblar_lista_partes()
        
        total_verts = sum(
            sum(sp['num_vertices'] for sp in p['subpartes'])
            for p in info['partes']
        )
        self.lbl_stats.configure(
            text=f"{info['cantidad_partes']} partes • {total_verts} vértices"
        )
        
        # Cargar huesos desde los bytes crudos del archivo
        with open(filepath, 'rb') as f:
            raw = bytearray(f.read())
        self._load_bones(raw)
        # Habilitar editor UVs si ya hay textura cargada
        if (hasattr(self, 'gl_viewport') and self.gl_viewport and
                self.gl_viewport.texture_id and
                not self.is_secondary_pmdl and hasattr(self, 'btn_edit_uvs')):
            self.btn_edit_uvs.configure(state="normal")
    
    def _load_from_data(self, pmdl_data, texture_path=None):
        """Carga PMDL desde bytearray (usado cuando se lanza desde el editor)"""
        try:
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.pmdl', delete=False) as tmp:
                tmp.write(pmdl_data)
                self.temp_pmdl_path = tmp.name
            
            # Analizar
            info, error = analizar_pmdl(self.temp_pmdl_path)
            
            if error:
                messagebox.showerror("Error", error)
                return
            
            self.pmdl_data = info
            self.lbl_archivo.configure(
                text=f"✅ Modelo desde editor ({info['tipo']})",
                text_color=("green", "lightgreen")
            )
            
            self.poblar_lista_partes()
            
            total_verts = sum(
                sum(sp['num_vertices'] for sp in p['subpartes'])
                for p in info['partes']
            )
            self.lbl_stats.configure(
                text=f"{info['cantidad_partes']} partes • {total_verts} vértices"
            )
            
            # Cargar textura si se proporcionó
            if texture_path and os.path.exists(texture_path):
                if GLViewport and hasattr(self, 'gl_viewport'):
                    if self.gl_viewport.load_texture(texture_path):
                        texture_name = os.path.basename(texture_path)
                        self.lbl_textura.configure(
                            text=f"🖼️ {texture_name}",
                            text_color=("green", "lightgreen")
                        )
            
            if not self.is_secondary_pmdl and hasattr(self, 'btn_edit_uvs'):
                self.btn_edit_uvs.configure(state="normal")
            
            self._load_bones(pmdl_data)
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el modelo: {e}")
    
    def poblar_lista_partes(self):
        for widget in self.partes_frame.winfo_children():
            widget.destroy()
        
        self.parte_buttons = {}
        
        btn_todo = ctk.CTkButton(
            self.partes_frame,
            text="TODO",
            command=lambda: self.seleccionar_parte(-1),
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("gray70", "gray25"),
            hover_color=("gray60", "gray30")
        )
        btn_todo.pack(fill="x", padx=5, pady=(5, 10))
        self.parte_buttons[-1] = btn_todo
        
        for parte in self.pmdl_data['partes']:
            btn_parte = ctk.CTkButton(
                self.partes_frame,
                text=f"Parte {parte['indice']:02d}",
                command=lambda idx=parte['indice']: self.seleccionar_parte(idx),
                height=36,
                font=ctk.CTkFont(size=13),
                fg_color=("gray75", "gray20"),
                hover_color=("gray65", "gray30"),
                corner_radius=6
            )
            btn_parte.pack(fill="x", padx=5, pady=3)
            self.parte_buttons[parte['indice']] = btn_parte
        
        self.seleccionar_parte(-1)
    
    def seleccionar_parte(self, indice, skip_uv_load=False):
        if not self.pmdl_data or not GLViewport:
            return
        
        if hasattr(self, 'parte_buttons'):
            for idx, btn in self.parte_buttons.items():
                if idx == indice:
                    btn.configure(fg_color=("#3B8ED0", "#1F6AA5"))
                else:
                    if idx == -1:
                        btn.configure(fg_color=("gray70", "gray25"))
                    else:
                        btn.configure(fg_color=("gray75", "gray20"))
        
        if indice == -1:
            mesh_data = self.procesar_todo()
            self.gl_viewport.set_mesh_data(mesh_data, viewing_mode='all', part_index=-1)
            self.lbl_controles.configure(
                text="🖱️ Scroll: Zoom • Rueda presionada: Rotar • Shift+Rueda: Mover • Click Izq: Seleccionar • ç o /: Aislar"
            )
        else:
            if indice < len(self.pmdl_data['partes']):
                parte = self.pmdl_data['partes'][indice]
                opacidad_normalizada = parte['opacidad'] / 65535.0
                mesh_data = self.procesar_parte(parte, (0.4, 0.7, 1.0), opacidad=opacidad_normalizada)
                self.gl_viewport.set_mesh_data(mesh_data, viewing_mode='single', part_index=indice)
                self.gl_viewport.isolated_part_index = indice
                self.lbl_controles.configure(
                    text=f"🖱️ Scroll: Zoom • Rueda presionada: Rotar • Shift+Rueda: Mover • Click Izq: Seleccionar subparte • ç o /: Regresar"
                )
        
        # Guardar parte seleccionada y actualizar UVs si el panel está visible
        self.parte_seleccionada = indice
        if not skip_uv_load and self.uv_panel_visible and self.uv_canvas:
            self.load_uvs_for_selected_part()
    
    def reseleccionar_parte(self, part_index):
        if not self.gl_viewport or not self.gl_viewport.mesh_data:
            return
        
        indices_to_select = set()
        for idx, mesh_data in enumerate(self.gl_viewport.mesh_data):
            if mesh_data.get('part_index') == part_index:
                indices_to_select.add(idx)
        
        if indices_to_select:
            self.gl_viewport.selected_parts = indices_to_select
            self.gl_viewport.redraw()
    
    def procesar_todo(self):
        mesh_data = []
        num_partes = len(self.pmdl_data['partes'])
        for idx, parte in enumerate(self.pmdl_data['partes']):
            hue = idx / max(num_partes, 1)
            color = colorsys.hsv_to_rgb(hue, 0.7, 0.95)
            opacidad_normalizada = parte['opacidad'] / 65535.0
            parte_mesh = self.procesar_parte(parte, color, part_index=idx, opacidad=opacidad_normalizada)
            mesh_data.extend(parte_mesh)
        return mesh_data
    
    def procesar_parte(self, parte, color, part_index=None, opacidad=1.0):
        GROSOR_MAXIMO = 68.0
        
        grosor_x = self.pmdl_data['grosor_x'] if self.pmdl_data['grosor_x'] > 0 else GROSOR_MAXIMO
        grosor_y = self.pmdl_data['grosor_y'] if self.pmdl_data['grosor_y'] > 0 else GROSOR_MAXIMO
        grosor_z = self.pmdl_data['grosor_z'] if self.pmdl_data['grosor_z'] > 0 else GROSOR_MAXIMO
        
        factor_x = grosor_x / GROSOR_MAXIMO
        factor_y = grosor_y / GROSOR_MAXIMO
        factor_z = grosor_z / GROSOR_MAXIMO
        
        mesh_data = []
        
        for subparte in parte['subpartes']:
            vertices_subparte = []
            triangulos_subparte = []
            
            for vertice in subparte['vertices']:
                x = vertice['coord_x'] * self.escala * factor_x * -1
                y = vertice['coord_y'] * self.escala * factor_y * -1
                z = vertice['coord_z'] * self.escala * factor_z
                
                vertices_subparte.append(np.array([x, y, z], dtype=float))
            
            uvs_subparte = []
            for vertice in subparte['vertices']:
                u = vertice['uv_x'] / 255.0
                v = 1.0 - (vertice['uv_y'] / 255.0)
                uvs_subparte.append([u, v])
            
            for i in range(len(vertices_subparte) - 2):
                if i % 2 == 0:
                    triangulo = [i, i + 1, i + 2]
                else:
                    triangulo = [i, i + 2, i + 1]
                triangulos_subparte.append(triangulo)
            
            if len(vertices_subparte) > 0:
                vertices_merged, uvs_merged, triangulos_merged = merge_vertices_by_distance(
                    vertices_subparte, uvs_subparte, triangulos_subparte, threshold=0.0001
                )
                data = {
                    'vertices': np.array(vertices_merged),
                    'triangulos': triangulos_merged,
                    'uvs': np.array(uvs_merged),
                    'color': color,
                    'opacidad': opacidad
                }
                if part_index is not None:
                    data['part_index'] = part_index
                mesh_data.append(data)
        
        return mesh_data
    
    def cleanup(self):
        if self.uv_editor_window and self.uv_editor_window.winfo_exists():
            try:
                self.uv_editor_window.destroy()
            except:
                pass
            self.uv_editor_window = None
        
        if self.temp_pmdl_path and os.path.exists(self.temp_pmdl_path):
            try:
                os.unlink(self.temp_pmdl_path)
            except:
                pass
        
        if self._temp_texture_owned and self.temp_texture_path and os.path.exists(self.temp_texture_path):
            try:
                os.unlink(self.temp_texture_path)
            except:
                pass
    
    def reload_pmdl_from_file(self, skip_uv_reload=False):
        if not self.temp_pmdl_path or not os.path.exists(self.temp_pmdl_path):
            return
        
        try:
            info, error = analizar_pmdl(self.temp_pmdl_path)
            
            if error:
                print(f"Error al recargar PMDL: {error}")
                return
            
            # Actualizar datos
            self.pmdl_data = info
            
            # Refrescar la visualización actual
            if hasattr(self, 'parte_buttons'):
                current_selection = self.parte_seleccionada if hasattr(self, 'parte_seleccionada') else -1
                
                # Solo repoblar lista si NO es skip_uv_reload
                if not skip_uv_reload:
                    # Repoblar lista de partes
                    self.poblar_lista_partes()
                
                if skip_uv_reload:
                    # Solo actualizar el 3D, no las UVs
                    if current_selection == -1:
                        mesh_data = self.procesar_todo()
                        self.gl_viewport.set_mesh_data(mesh_data, viewing_mode='all', part_index=-1)
                    elif current_selection < len(self.pmdl_data['partes']):
                        parte = self.pmdl_data['partes'][current_selection]
                        opacidad_normalizada = parte['opacidad'] / 65535.0
                        mesh_data = self.procesar_parte(parte, (0.4, 0.7, 1.0), opacidad=opacidad_normalizada)
                        self.gl_viewport.set_mesh_data(mesh_data, viewing_mode='single', part_index=current_selection)
                else:
                    # Recargar todo incluyendo UVs
                    if current_selection >= 0:
                        self.seleccionar_parte(current_selection)
                    else:
                        self.seleccionar_parte(-1)
            
            print("✓ Modelo 3D actualizado con cambios de UVs")
            
        except Exception as e:
            print(f"Error al recargar PMDL: {e}")
    
    def _on_window_resize(self, event):
        # Ignorar eventos que no son de la ventana principal
        if event.widget != self:
            return
        
        # Ignorar eventos de movimiento
        if hasattr(self, '_last_size'):
            if (event.width, event.height) == self._last_size:
                return
        
        self._last_size = (event.width, event.height)
        
        # Cancelar timer anterior si existe
        if hasattr(self, '_resize_timer'):
            self.after_cancel(self._resize_timer)
        
        self._resize_timer = self.after(100, self._do_window_resize)
    
    def _do_window_resize(self):
        """Ejecuta la actualización real de OpenGL"""
        if hasattr(self, 'gl_viewport') and self.gl_viewport:
            try:
                if self.gl_viewport.winfo_exists():
                    # Mini rotación para refrescar el viewport
                    self.gl_viewport.trigger_mini_rotation()
                    self.gl_viewport.update()
            except:
                pass
    
    def _global_undo(self, event=None):
        """Undo global - delega al canvas UV si está visible"""
        if self.uv_panel_visible and self.uv_canvas:
            self.uv_canvas._undo()
        return "break"
    
    def _global_redo(self, event=None):
        """Redo global - delega al canvas UV si está visible"""
        if self.uv_panel_visible and self.uv_canvas:
            self.uv_canvas._redo()
        return "break"
    
    def create_splitter(self):
        """Crea el divisor arrastrable entre el 3D y el panel UV"""
        self.splitter = ctk.CTkFrame(self, width=4, corner_radius=0, fg_color=("gray60", "gray40"))
        self.splitter.grid(row=1, column=2, sticky="ns", padx=0, pady=0)
        self.splitter.grid_propagate(False)
        
        # Forzar el width mínimo
        self.splitter.configure(width=4)
        
        # Cambiar cursor al pasar sobre el splitter
        self.splitter.bind("<Enter>", lambda e: self.splitter.configure(cursor="sb_h_double_arrow"))
        self.splitter.bind("<Leave>", lambda e: self.splitter.configure(cursor=""))
        
        # Bindings para arrastrar
        self.splitter.bind("<Button-1>", self.on_splitter_press)
        self.splitter.bind("<B1-Motion>", self.on_splitter_drag)
        self.splitter.bind("<ButtonRelease-1>", self.on_splitter_release)
        
        self.splitter_dragging = False
        self.splitter_start_x = 0
    
    def on_splitter_press(self, event):
        """Inicia el arrastre del splitter"""
        self.splitter_dragging = True
        self.splitter_start_x = event.x_root
        self.splitter_start_width = self.uv_panel_width
    
    def on_splitter_drag(self, event):
        """Arrastra el splitter para redimensionar"""
        if not self.splitter_dragging:
            return
        
        # Calcular el cambio en X
        delta_x = self.splitter_start_x - event.x_root
        new_width = self.splitter_start_width + delta_x
        
        # Limitar el ancho del panel UV
        min_width = 300
        max_width = 800
        new_width = max(min_width, min(max_width, new_width))
        
        # Aplicar nuevo ancho
        self.uv_panel_width = new_width
        
        if self.uv_panel:
            self.uv_panel.configure(width=new_width)
            self.grid_columnconfigure(3, minsize=new_width)
    
    def on_splitter_release(self, event):
        """Termina el arrastre del splitter"""
        self.splitter_dragging = False
        
        # Forzar redibujado del OpenGL al terminar
        self.update_idletasks()
        if hasattr(self, 'gl_viewport') and self.gl_viewport:
            self.after(50, self._force_gl_redraw)
    
    def _force_gl_redraw(self):
        """Fuerza el redibujado del viewport OpenGL"""
        if hasattr(self, 'gl_viewport') and self.gl_viewport and self.gl_viewport.winfo_exists():
            try:
                self.gl_viewport.redraw()
            except:
                pass
    
    def _on_window_move_start(self, event):
        """Se llama al empezar a mover la ventana (reduce lag)"""
        # Solo si el click es en el título de la ventana
        if event.y < 30:
            self._window_moving = True
    
    def _on_window_move_end(self, event):
        """Se llama al terminar de mover la ventana"""
        if hasattr(self, '_window_moving') and self._window_moving:
            self._window_moving = False
            # Forzar redibujado al terminar de mover
            self.after(50, self._force_gl_redraw)
            
    def toggle_uv_panel(self):
        """Toggle para mostrar/ocultar el panel de UVs"""
        if self.uv_panel_visible:
            # Ocultar panel y splitter
            if self.uv_panel:
                self.uv_panel.grid_forget()
            if hasattr(self, 'splitter') and self.splitter:
                self.splitter.grid_forget()
            # Resetear minsize de la columna
            self.grid_columnconfigure(3, minsize=0)
            self.uv_panel_visible = False
            self.btn_edit_uvs.configure(
                fg_color=("#FF8C00", "#FF6F00"),
                hover_color=("#FF7F00", "#FF5500")
            )
            # Forzar redibujado completo del OpenGL
            self.update_idletasks()
            self.after(100, self._force_gl_redraw)
        else:
            # Mostrar panel y splitter
            if not self.uv_panel:
                self.create_uv_panel()
            else:
                # Re-aplicar el ancho guardado y minsize
                self.uv_panel.configure(width=self.uv_panel_width)
                self.grid_columnconfigure(3, minsize=self.uv_panel_width)
                if hasattr(self, 'splitter') and self.splitter:
                    self.splitter.grid(row=1, column=2, sticky="ns", padx=0, pady=0)
                self.uv_panel.grid(row=1, column=3, sticky="nsew", padx=0, pady=0)
            self.uv_panel_visible = True
            
            # Forzar actualización del viewport OpenGL
            self.update_idletasks()
            self.after(50, self._force_gl_redraw)
                
            self.btn_edit_uvs.configure(
                fg_color=("#FFA500", "#FF8C00"),
                hover_color=("#FFB520", "#FFA000")
            )
            # NO cargar UVs automáticamente — solo se cargan al clicar parte o botón TODO

    def create_uv_panel(self):
        """Crea el panel lateral de UVs con splitter redimensionable"""
        # Inicializar ancho solo si no existe
        if not hasattr(self, 'uv_panel_width'):
            self.uv_panel_width = 450
        
        self.uv_panel = ctk.CTkFrame(self, width=self.uv_panel_width, corner_radius=0)
        self.uv_panel.grid(row=1, column=3, sticky="nsew", padx=0, pady=0)
        self.uv_panel.grid_propagate(False)
        self.uv_panel.grid_columnconfigure(0, weight=1)
        self.uv_panel.grid_rowconfigure(1, weight=1)
        
        # Establecer minsize en la columna para mantener el ancho
        self.grid_columnconfigure(3, minsize=self.uv_panel_width)
        
        # Crear splitter solo si no existe
        if not hasattr(self, 'splitter') or not self.splitter:
            self.create_splitter()
        
        # Header
        header = ctk.CTkFrame(self.uv_panel, height=50, corner_radius=0, fg_color=("gray85", "gray20"))
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=0)  # título fijo
        header.grid_columnconfigure(1, weight=1)  # coord_label expande
        
        title = ctk.CTkLabel(
            header, text="Editor de UVs",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title.grid(row=0, column=0, padx=(15, 8), pady=12, sticky="w")
        
        # Coord label al lado del título — más grande y visible
        self.coord_label = ctk.CTkLabel(
            header, text="By - Los ijue30s",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#FF8C00", "#FFB347")
        )
        self.coord_label.grid(row=0, column=1, padx=4, pady=12, sticky="w")
        
        # Botones V, I, F
        mode_frame = ctk.CTkFrame(header, fg_color="transparent")
        mode_frame.grid(row=0, column=2, padx=10, pady=8)
        
        self.btn_vertex_mode = ctk.CTkButton(
            mode_frame, text="V", width=35, height=30,
            command=lambda: self.set_uv_selection_mode("vertex"),
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            border_width=2,
            border_color="#FF7F00",
            text_color="#FF7F00",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_vertex_mode.grid(row=0, column=0, padx=2)
        
        self.btn_island_mode = ctk.CTkButton(
            mode_frame, text="I", width=35, height=30,
            command=lambda: self.set_uv_selection_mode("island"),
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            border_width=2,
            border_color="#555",
            text_color="#999",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_island_mode.grid(row=0, column=1, padx=2)
        
        self.btn_face_mode = ctk.CTkButton(
            mode_frame, text="F", width=35, height=30,
            command=lambda: self.set_uv_selection_mode("face"),
            fg_color="#2a2a2a",
            hover_color="#3a3a3a",
            border_width=2,
            border_color="#555",
            text_color="#999",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_face_mode.grid(row=0, column=2, padx=2)
        
        # Canvas container
        canvas_container = ctk.CTkFrame(self.uv_panel, fg_color="transparent")
        canvas_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
        
        # UV Canvas
        self.uv_canvas = UVCanvas(canvas_container, bg="#2b2b2b", highlightthickness=0)
        self.uv_canvas.grid(row=0, column=0, sticky="nsew")
        self.uv_canvas.editor = self
        
        # Footer
        footer = ctk.CTkFrame(self.uv_panel, height=55, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        
        self.btn_save_uvs = ctk.CTkButton(
            footer, text="💾 Guardar Cambios",
            command=self.save_uvs,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#28a745", "#1e7e34"),
            hover_color=("#218838", "#155724")
        )
        self.btn_save_uvs.pack(padx=15, pady=8, fill="x")
        
        # coord_label ahora está en el header — conectar referencia al canvas
        self.uv_canvas.coord_label = self.coord_label
        
        # Cargar textura inmediatamente si existe
        if self.temp_texture_path and os.path.exists(self.temp_texture_path):
            self.uv_canvas.load_texture(self.temp_texture_path)

    def load_uvs_for_selected_part(self):
        """Carga las UVs de la parte seleccionada en el canvas"""
        if not self.temp_pmdl_path or not self.uv_canvas:
            return
        
        try:
            # Crear parser si no existe
            if not self.uv_parser:
                self.uv_parser = PmdlParser(self.temp_pmdl_path)
                if not self.uv_parser.analyze():
                    print("Error al analizar PMDL para UVs")
                    return
            
            # Cargar textura en canvas si existe
            if self.temp_texture_path and os.path.exists(self.temp_texture_path):
                if not self.uv_canvas.load_texture(self.temp_texture_path):
                    print("Error al cargar textura en canvas UV")
            
            # Obtener índice de parte seleccionada
            if not hasattr(self, 'parte_seleccionada') or self.parte_seleccionada is None:
                # Seleccionar la primera parte por defecto
                if self.uv_parser.part_count > 0:
                    self.parte_seleccionada = 0
                else:
                    return
            
            # Dibujar UVs de la parte seleccionada
            if self.parte_seleccionada == -1:
                todas_las_partes = list(range(self.uv_parser.part_count))
                self.uv_canvas.draw_uvs(self.uv_parser.parts_data, todas_las_partes)
                print(f"✓ UVs cargadas: TODAS las partes ({len(todas_las_partes)} partes)")
            else:
                self.uv_canvas.draw_uvs(self.uv_parser.parts_data, [self.parte_seleccionada])
                print(f"✓ UVs cargadas: Parte {self.parte_seleccionada}")
            
        except Exception as e:
            print(f"Error al cargar UVs: {e}")
            import traceback
            traceback.print_exc()

    def set_uv_selection_mode(self, mode):
        """Cambia el modo de selección en el canvas UV"""
        if not self.uv_canvas:
            return
        
        # Actualizar modo en el canvas
        self.uv_canvas.selection_mode = mode
        self.uv_canvas._update_visibility_by_mode()
        self.uv_canvas._deselect_all()
        
        self.btn_vertex_mode.configure(
            fg_color="#3a3a3a" if mode == "vertex" else "#2a2a2a",
            border_color="#FF7F00" if mode == "vertex" else "#555",
            text_color="#FF7F00" if mode == "vertex" else "#999"
        )
        self.btn_island_mode.configure(
            fg_color="#3a3a3a" if mode == "island" else "#2a2a2a",
            border_color="#FF7F00" if mode == "island" else "#555",
            text_color="#FF7F00" if mode == "island" else "#999"
        )
        self.btn_face_mode.configure(
            fg_color="#3a3a3a" if mode == "face" else "#2a2a2a",
            border_color="#FF7F00" if mode == "face" else "#555",
            text_color="#FF7F00" if mode == "face" else "#999"
        )

    def save_uvs(self):
        """Guarda los cambios de UVs y recarga el modelo 3D"""
        if not self.uv_parser or not self.temp_pmdl_path:
            messagebox.showerror("Error", "No hay UVs para guardar")
            return
        
        try:
            # Guardar UVs
            if self.uv_parser.save_uvs(self.uv_parser.parts_data, self.temp_pmdl_path):
                print("✓ UVs guardadas")
                # Marcar como guardado
                self.has_unsaved_changes = True
                # Recargar modelo 3D sin cambiar el modo actual
                self.reload_pmdl_from_file(skip_uv_reload=True)
            else:
                messagebox.showerror("Error", "No se pudieron guardar las UVs")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar UVs: {e}")
            import traceback
            traceback.print_exc()

    def mark_as_modified(self):
        """Marca que hay cambios sin guardar (llamado desde canvas)"""
        pass
    
    def get_modified_pmdl_data(self):
        """Devuelve el bytearray del PMDL modificado solo si fue heredado del editor principal."""
        if getattr(self, 'pmdl_origin', 'inherited') == 'explicit':
            return None
        if self.temp_pmdl_path and os.path.exists(self.temp_pmdl_path):
            try:
                with open(self.temp_pmdl_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                print(f"Error al leer PMDL modificado: {e}")
        return None

    def auto_save_preview(self):
        """Auto-guarda y recarga modelo 3D (llamado desde canvas al terminar G/S/Undo/Redo)"""
        if not self.uv_parser or not self.temp_pmdl_path:
            return
        
        try:
            # Guardar silenciosamente
            if self.uv_parser.save_uvs(self.uv_parser.parts_data, self.temp_pmdl_path):
                info, error = analizar_pmdl(self.temp_pmdl_path)
                
                if not error and info:
                    self.pmdl_data = info
                    
                    # Actualizar solo el 3D según la parte actual
                    if hasattr(self, 'parte_seleccionada') and self.parte_seleccionada is not None:
                        if self.parte_seleccionada == -1:
                            # Modo TODO
                            mesh_data = self.procesar_todo()
                            if hasattr(self, 'gl_viewport') and self.gl_viewport:
                                self.gl_viewport.set_mesh_data(mesh_data, viewing_mode='all', part_index=-1)
                        elif self.parte_seleccionada < len(self.pmdl_data['partes']):
                            # Parte específica
                            parte = self.pmdl_data['partes'][self.parte_seleccionada]
                            opacidad_normalizada = parte['opacidad'] / 65535.0
                            mesh_data = self.procesar_parte(parte, (0.4, 0.7, 1.0), opacidad=opacidad_normalizada)
                            if hasattr(self, 'gl_viewport') and self.gl_viewport:
                                self.gl_viewport.set_mesh_data(mesh_data, viewing_mode='single', part_index=self.parte_seleccionada)
                    
                    
        except Exception as e:
            print(f"Error en auto_save_preview: {e}")
            import traceback
            traceback.print_exc()    
    def _load_bones(self, pmdl_data):
        try:
            from app.logic_3d.bones.bones_reader import leer_armature_pmdl, cargar_nombres_huesos
            
            bones_data = leer_armature_pmdl(pmdl_data)
            bones_names = cargar_nombres_huesos()
            
            if bones_data and hasattr(self, 'gl_viewport') and self.gl_viewport:
                self.gl_viewport.set_bones_data(bones_data, bones_names)
        except Exception as e:
            print(f"Error cargando huesos: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_bones(self):
        if hasattr(self, 'gl_viewport') and self.gl_viewport:
            visible = self.gl_viewport.toggle_bones()
            
            if visible:
                self.btn_bones.configure(fg_color=("#9C27B0", "#7B1FA2"), hover_color=("#7B1FA2", "#6A1B9A"))
            else:
                self.btn_bones.configure(fg_color=("gray75", "gray25"), hover_color=("gray65", "gray30"))

    def _write_info(self, segments):
        if not hasattr(self, 'info_label') or not isinstance(self.info_label, tk.Text):
            return
        self.info_label.configure(state="normal")
        self.info_label.delete("1.0", "end")
        if not segments:
            self.info_label.place_forget()
            self.info_label.configure(state="disabled")
            return
        for text, tag in segments:
            self.info_label.insert("end", text, tag)
        self.info_label.configure(state="disabled")
        content_str = "".join(t for t, _ in segments)
        nlines = content_str.count(chr(10)) + 1
        max_w = max((len(l) for l in content_str.split(chr(10))), default=10)
        self.info_label.configure(height=nlines, width=max(18, max_w + 2))
        self.info_label.place(relx=1.0, rely=0.0, x=-30, y=30, anchor="ne")

    def update_bone_info(self, bone):
        bone_id = bone["bone_id"]
        sk_name = f"sk_{bone_id:02X}"
        renamed = self.gl_viewport.bones_names.get(sk_name, "") if hasattr(self.gl_viewport, "bones_names") else ""
        is_root = bone["padre_idx"] is None
        pos     = bone["pos_visor"]
        nl = chr(10)
        segs = [(f"Hueso {bone_id:02X}", "bold_white"), (nl, "normal_white")]
        if renamed:
            segs += [(renamed, "bold_yellow"), (nl, "normal_white")]
        if is_root:
            segs += [("Hueso Padre", "bold_white"), (" - (Raiz)", "light_gray"), (nl, "normal_white")]
        else:
            padre = self.gl_viewport.bones_data[bone["padre_idx"]]
            pid   = padre["bone_id"]
            psk   = f"sk_{pid:02X}"
            pname = self.gl_viewport.bones_names.get(psk, "") if hasattr(self.gl_viewport, "bones_names") else ""
            segs += [("Hijo de: ", "bold_white"), (f"Hueso {pid:02X}", "normal_white"), (nl, "normal_white")]
            if pname:
                segs += [(pname, "yellow"), (nl, "normal_white")]
        segs += [("X:", "bold_white"), (f" {pos[0]:.3f}" + nl, "normal_white")]
        segs += [("Y:", "bold_white"), (f" {pos[1]:.3f}" + nl, "normal_white")]
        segs += [("Z:", "bold_white"), (f" {pos[2]:.3f}", "normal_white")]
        self._write_info(segs)

    def clear_bone_info(self):
        self._write_info([])