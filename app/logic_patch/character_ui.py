import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
from PIL import Image, ImageTk
import os


class CharacterEditorUI(ctk.CTkToplevel):
    
    def __init__(self, parent, is_secondary=False, on_open_in_editor_callback=None):
        super().__init__(parent)
        
        self.parent = parent
        self.is_secondary = is_secondary
        self.on_open_in_editor_callback = on_open_in_editor_callback
        
        # Importar después de crear la ventana
        from app.logic_patch import CharacterAnalyzer
        
        self.analyzer = CharacterAnalyzer()
        self.texture_image = None
        self.current_ctk_image = None
        
        # Configuración de ventana
        title_text = "DBZ TTT Character Editor (Secundario)" if is_secondary else "DBZ TTT Character Editor"
        self.title(title_text)
        self.geometry("700x700")
        self.minsize(600, 600)
        
        # Hacer modal
        self.transient(parent)
        self.grab_set()
        
        # Centrar ventana
        from app.utils import center_window
        self.after(10, lambda: center_window(self, 700, 700))
        
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz."""
        # Configurar grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Frame principal
        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # ===== HEADER =====
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 20))
        
        title_text = "Character Editor (Secundario)" if self.is_secondary else "Character Editor"
        title = ctk.CTkLabel(
            header_frame,
            text=title_text,
            font=("Segoe UI", 24, "bold"),
            text_color=("#DB4437", "#DB4437")
        )
        title.pack()
        
        subtitle_text = "Solo lectura - Exportar textura" if self.is_secondary else "Edita texturas y exporta PMDL"
        subtitle = ctk.CTkLabel(
            header_frame,
            text=subtitle_text,
            font=("Segoe UI", 12),
            text_color=("gray60", "gray40")
        )
        subtitle.pack(pady=(5, 0))
        
        # ===== BOTÓN DE CARGA =====
        load_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        load_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 10))
        
        self.load_btn = ctk.CTkButton(
            load_frame,
            text="Cargar Personaje",
            command=self.load_character,
            height=40,
            font=("Segoe UI", 14, "bold"),
            corner_radius=8,
            fg_color=("#2196F3", "#1976D2"),
            hover_color=("#1976D2", "#1565C0")
        )
        self.load_btn.pack(fill="x")
        
        # ===== BOTÓN ABRIR PMDL EN EDITOR =====
        if self.on_open_in_editor_callback:
            self.open_in_editor_btn = ctk.CTkButton(
                load_frame,
                text="🔧 Abrir PMDL en el Editor",
                command=self._on_open_in_editor,
                height=40,
                font=("Segoe UI", 14, "bold"),
                corner_radius=8,
                state="disabled",
                fg_color=("#FF9800", "#F57C00"),
                hover_color=("#F57C00", "#E65100")
            )
            self.open_in_editor_btn.pack(fill="x", pady=(10, 0))
            
            # ===== BOTÓN Y DROPDOWN PARA CARAS EXTRA (PMDFS) =====
            self.faces_frame = ctk.CTkFrame(load_frame, fg_color="transparent")
            # No se muestra hasta que se detecten caras
            
            self.open_face_btn = ctk.CTkButton(
                self.faces_frame,
                text="Abrir PMDF en el Editor",
                command=self._on_open_face_in_editor,
                height=38,
                font=("Segoe UI", 13, "bold"),
                corner_radius=8,
                fg_color=("#9C27B0", "#7B1FA2"),
                hover_color=("#7B1FA2", "#6A1B9A")
            )
            self.open_face_btn.pack(side="left", fill="both", expand=True, padx=(0, 8))
            
            self.face_dropdown = ctk.CTkOptionMenu(
                self.faces_frame,
                values=["Cara de daño"],
                height=38,
                font=("Segoe UI", 12),
                corner_radius=8,
                fg_color=("#673AB7", "#512DA8"),
                button_color=("#512DA8", "#4527A0"),
                button_hover_color=("#4527A0", "#311B92")
            )
            self.face_dropdown.pack(side="right", padx=0)
        
        # ===== ÁREA DE TEXTURA =====
        texture_container = ctk.CTkFrame(main_frame, corner_radius=12)
        texture_container.grid(row=2, column=0, sticky="nsew", padx=30, pady=(10, 20))
        texture_container.grid_rowconfigure(1, weight=1)
        texture_container.grid_columnconfigure(0, weight=1)
        
        # Header de textura
        tex_header = ctk.CTkFrame(texture_container, fg_color="transparent", height=40)
        tex_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        
        tex_title = ctk.CTkLabel(
            tex_header,
            text="Textura del Personaje",
            font=("Segoe UI", 15, "bold")
        )
        tex_title.pack(side="left")
        
        self.texture_info_label = ctk.CTkLabel(
            tex_header,
            text="",
            font=("Segoe UI", 10),
            text_color=("gray50", "gray50")
        )
        self.texture_info_label.pack(side="right")
        
        # Frame para la imagen
        self.texture_frame = ctk.CTkFrame(texture_container, fg_color="transparent")
        self.texture_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
        self.texture_frame.grid_rowconfigure(0, weight=1)
        self.texture_frame.grid_columnconfigure(0, weight=1)
        
        # Label para mostrar textura
        self.texture_label = ctk.CTkLabel(
            self.texture_frame,
            text="No hay textura cargada\n\nCarga un personaje para comenzar",
            font=("Segoe UI", 12),
            text_color=("gray50", "gray50")
        )
        self.texture_label.grid(row=0, column=0)
        
        # Menú contextual para la textura
        self.texture_menu = Menu(self, tearoff=0)
        self.texture_menu.add_command(
            label="📤 Exportar Textura",
            command=self.export_texture_dialog
        )
        self.texture_menu.add_command(
            label="📦 Exportar Raw (.atex)",
            command=self.export_texture_raw_dialog
        )
        
        if not self.is_secondary:
            self.texture_menu.add_command(
                label="📥 Importar Textura",
                command=self.import_texture_dialog
            )
            self.texture_menu.add_command(
                label="📂 Importar Raw (.atex/.unk)",
                command=self.import_texture_raw_dialog
            )
        
        self.texture_label.bind("<Button-3>", self.show_texture_menu)
        
        # ===== BOTONES DE ACCIÓN =====
        if not self.is_secondary:
            actions_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            actions_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 30))
            actions_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
            
            self.export_pmdl_btn = ctk.CTkButton(
                actions_frame,
                text="📤 Exportar pMdl",
                command=self.export_pmdl_dialog,
                height=36,
                font=("Segoe UI", 12, "bold"),
                state="disabled",
                corner_radius=8,
                fg_color=("#757575", "#616161"),
                hover_color=("#616161", "#424242")
            )
            self.export_pmdl_btn.grid(row=0, column=0, padx=4, sticky="ew")
            
            self.import_pmdl_btn = ctk.CTkButton(
                actions_frame,
                text="📥 Importar pMdl",
                command=self.import_pmdl_dialog,
                height=36,
                font=("Segoe UI", 12, "bold"),
                state="disabled",
                corner_radius=8,
                fg_color=("#757575", "#616161"),
                hover_color=("#616161", "#424242")
            )
            self.import_pmdl_btn.grid(row=0, column=1, padx=4, sticky="ew")
            
            self.save_btn = ctk.CTkButton(
                actions_frame,
                text="💾 Guardar",
                command=self.save_character,
                height=36,
                font=("Segoe UI", 12, "bold"),
                state="disabled",
                corner_radius=8,
                fg_color=("#4CAF50", "#388E3C"),
                hover_color=("#388E3C", "#2E7D32")
            )
            self.save_btn.grid(row=0, column=2, padx=4, sticky="ew")
            
            self.save_as_btn = ctk.CTkButton(
                actions_frame,
                text="💾 Guardar Como",
                command=self.save_character_as,
                height=36,
                font=("Segoe UI", 12, "bold"),
                state="disabled",
                corner_radius=8,
                fg_color=("#4CAF50", "#388E3C"),
                hover_color=("#388E3C", "#2E7D32")
            )
            self.save_as_btn.grid(row=0, column=3, padx=4, sticky="ew")
    
    def load_character(self):
        """Carga y analiza un archivo de personaje."""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo de personaje",
            filetypes=[
                ("Archivos de personaje", "*.PCK1 *.pak"),
                ("Todos los archivos", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        if self.analyzer.load_file(file_path):
            if self.analyzer.find_pmdl_and_texture():
                self.display_texture()
                self.enable_buttons()
                messagebox.showinfo("Éxito", f"Personaje cargado:\n{os.path.basename(file_path)}")
            else:
                messagebox.showerror("Error", "No se pudo encontrar pMdl o textura en el archivo")
        else:
            messagebox.showerror("Error", "No se pudo cargar el archivo")
    
    def load_character_from_path(self, file_path):
        """Carga un personaje desde una ruta específica (usado por el controlador)."""
        if self.analyzer.load_file(file_path):
            if self.analyzer.find_pmdl_and_texture():
                self.display_texture()
                self.enable_buttons()
                return True
        return False
    
    def display_texture(self):
        """Muestra la textura del personaje."""
        img = self.analyzer.generate_texture_image()
        if img:
            # Redimensionar imagen para caber en el frame
            max_width = 600
            max_height = 350
            
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convertir a CTkImage
            self.current_ctk_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(img.width, img.height)
            )
            
            self.texture_label.configure(image=self.current_ctk_image, text="")
            self.texture_image = img
            
            # Actualizar info
            if self.analyzer.texture_info:
                size_kb = self.analyzer.texture_info['size'] / 1024
                self.texture_info_label.configure(
                    text=f"{img.width}x{img.height} • {size_kb:.1f} KB"
                )
        else:
            self.texture_label.configure(image="", text="Error al cargar textura")
    
    def enable_buttons(self):
        """Habilita los botones después de cargar un personaje."""
        if hasattr(self, 'open_in_editor_btn'):
            self.open_in_editor_btn.configure(state="normal")
        
        # Detectar y mostrar caras extra
        if hasattr(self, 'on_open_in_editor_callback') and self.on_open_in_editor_callback:
            self._detect_and_show_extra_faces()
        
        if not self.is_secondary:
            self.export_pmdl_btn.configure(state="normal")
            self.import_pmdl_btn.configure(state="normal")
            self.save_btn.configure(state="normal")
            self.save_as_btn.configure(state="normal")
    
    def _detect_and_show_extra_faces(self):
        """Detecta caras extra y muestra el botón + dropdown si existen."""
        faces = self.analyzer.find_extra_faces()
        
        if faces:
            # Actualizar dropdown con las caras encontradas
            face_names = list(faces.keys())
            self.face_dropdown.configure(values=face_names)
            self.face_dropdown.set(face_names[0])  # Seleccionar la primera
            
            # Mostrar frame de caras
            self.faces_frame.pack(fill="x", pady=(10, 0))
        else:
            # Ocultar frame si no hay caras
            if hasattr(self, 'faces_frame'):
                self.faces_frame.pack_forget()
    
    def show_texture_menu(self, event):
        """Muestra el menú contextual de la textura."""
        if self.analyzer.texture_info:
            self.texture_menu.post(event.x_root, event.y_root)
    
    def export_texture_dialog(self):
        """Exporta la textura a un archivo PNG."""
        if not self.analyzer.texture_info:
            messagebox.showwarning("Advertencia", "No hay textura cargada")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Exportar textura",
            defaultextension=".png",
            filetypes=[("Imágenes PNG", "*.png")]
        )
        
        if file_path:
            if self.analyzer.export_texture(file_path):
                messagebox.showinfo("Éxito", f"Textura exportada:\n{file_path}")
            else:
                messagebox.showerror("Error", "No se pudo exportar la textura")
    
    def import_texture_dialog(self):
        """Importa una textura desde un archivo PNG."""
        if not self.analyzer.texture_info:
            messagebox.showwarning("Advertencia", "Primero carga un personaje")
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar textura",
            filetypes=[("Imágenes PNG", "*.png"), ("Todas las imágenes", "*.png *.jpg *.jpeg")]
        )
        
        if file_path:
            if self.analyzer.import_texture(file_path):
                self.display_texture()
                messagebox.showinfo("Éxito", "Textura importada correctamente")
            else:
                messagebox.showerror("Error", "No se pudo importar la textura")
    
    def export_texture_raw_dialog(self):
        if not self.analyzer.texture_info:
            messagebox.showwarning("Advertencia", "No hay textura cargada")
            return
        file_path = filedialog.asksaveasfilename(
            title="Exportar textura RAW",
            initialfile="011_textures.atex",
            defaultextension=".atex",
            filetypes=[("Textura RAW", "*.atex"), ("Todos", "*.*")]
        )
        if file_path:
            try:
                start = self.analyzer.texture_info['start']
                end   = self.analyzer.texture_info['end']
                with open(file_path, 'wb') as f:
                    f.write(self.analyzer.file_data[start:end])
                messagebox.showinfo("Éxito", f"Textura RAW exportada:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def import_texture_raw_dialog(self):
        if not self.analyzer.texture_info:
            messagebox.showwarning("Advertencia", "Primero carga un personaje")
            return
        file_path = filedialog.askopenfilename(
            title="Importar textura RAW",
            filetypes=[("Textura RAW", "*.atex *.unk"), ("Todos", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            from app.utils.atex_reader import atex_to_pil
            atex_to_pil(raw_data)  # validar que sea legible
        except Exception as e:
            messagebox.showerror("Error", f"Archivo RAW inválido:\n{e}")
            return
        if self.analyzer.import_texture_raw(raw_data):
            self.display_texture()
            messagebox.showinfo("Éxito", "Textura RAW importada correctamente")
        else:
            messagebox.showerror("Error", "No se pudo importar la textura RAW")

    def export_pmdl_dialog(self):
        """Exporta el pMdl a un archivo."""
        if not self.analyzer.pmdl_info:
            messagebox.showwarning("Advertencia", "No hay pMdl cargado")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Exportar pMdl",
            defaultextension=".pmdl",
            filetypes=[("Archivos PMDL", "*.pmdl")]
        )
        
        if file_path:
            if self.analyzer.export_pmdl(file_path):
                messagebox.showinfo("Éxito", f"pMdl exportado:\n{file_path}")
            else:
                messagebox.showerror("Error", "No se pudo exportar el pMdl")
    
    def import_pmdl_dialog(self):
        """Importa un pMdl desde un archivo."""
        if not self.analyzer.pmdl_info:
            messagebox.showwarning("Advertencia", "Primero carga un personaje")
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar pMdl",
            filetypes=[("Archivos PMDL", "*.pmdl")]
        )
        
        if file_path:
            if self.analyzer.import_pmdl(file_path):
                messagebox.showinfo("Éxito", "pMdl importado correctamente")
            else:
                messagebox.showerror("Error", "No se pudo importar el pMdl")
    
    def save_character(self):
        """Guarda el personaje en el archivo original."""
        if not self.analyzer.file_path:
            messagebox.showwarning("Advertencia", "No hay archivo cargado")
            return
        
        if messagebox.askyesno("Confirmar", "¿Guardar cambios en el archivo original?"):
            if self.analyzer.save_file():
                messagebox.showinfo("Éxito", "Personaje guardado correctamente")
            else:
                messagebox.showerror("Error", "No se pudo guardar el archivo")
    
    def save_character_as(self):
        """Guarda el personaje en un nuevo archivo."""
        file_path = filedialog.asksaveasfilename(
            title="Guardar personaje como",
            defaultextension=".PCK1",
            filetypes=[("Archivos PCK1", "*.PCK1"), ("Archivos PAK", "*.pak")]
        )
        
        if file_path:
            if self.analyzer.save_file(file_path):
                messagebox.showinfo("Éxito", f"Personaje guardado:\n{file_path}")
            else:
                messagebox.showerror("Error", "No se pudo guardar el archivo")
    
    def _on_open_in_editor(self):
        """Callback para abrir el PMDL en el editor principal."""
        if self.on_open_in_editor_callback and self.analyzer.pmdl_info:
            self.on_open_in_editor_callback(self.analyzer)
    
    def _on_open_face_in_editor(self):
        """Callback para abrir un PMDF (cara extra) en el editor principal."""
        if not self.on_open_in_editor_callback:
            return
        
        # Obtener cara seleccionada
        selected_face = self.face_dropdown.get()
        
        # Verificar que exista
        faces = self.analyzer.find_extra_faces()
        if selected_face not in faces:
            messagebox.showerror("Error", f"No se encontró la cara: {selected_face}")
            return
        
        face_analyzer = FaceAnalyzerWrapper(self.analyzer, selected_face)
        
        # Llamar al callback con el wrapper
        self.on_open_in_editor_callback(face_analyzer)
    
    def get_analyzer(self):
        """Retorna el analizador de personajes."""
        return self.analyzer


class FaceAnalyzerWrapper:
    """
    Wrapper que hace que una cara extra (PMDF) se comporte como un PMDL completo.
    Permite editarla y guardarla de vuelta en el parche.
    """
    def __init__(self, parent_analyzer, face_name):
        self.parent_analyzer = parent_analyzer
        self.face_name = face_name
        self.file_path = parent_analyzer.file_path
        
        # Obtener info de la cara
        faces = parent_analyzer.find_extra_faces()
        if face_name not in faces:
            raise ValueError(f"Cara {face_name} no encontrada")
        
        self.face_info = faces[face_name]
        
        # Crear un pmdl_info fake que apunte a la cara
        self.pmdl_info = {
            'start': self.face_info['start'],
            'end': self.face_info['end'],
            'size': self.face_info['size']
        }
        
        # Copiar file_data del parent
        self.file_data = parent_analyzer.file_data
        self.texture_info = parent_analyzer.texture_info
    
    def get_pmdl_data(self):
        """Obtiene los datos del PMDF como si fuera un PMDL."""
        return bytearray(self.file_data[self.face_info['start']:self.face_info['end']])
    
    def set_pmdl_data(self, new_data):
        """Actualiza el PMDF en el parche."""
        return self.parent_analyzer.set_face_data(self.face_name, new_data)
    
    def save_patch(self):
        """Guarda el parche completo."""
        return self.parent_analyzer.save_file()
    
    def generate_texture_image(self):
        """Genera la imagen de textura."""
        return self.parent_analyzer.generate_texture_image()