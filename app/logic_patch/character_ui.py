import customtkinter as ctk
from tkinter import filedialog, messagebox, Menu
from PIL import Image, ImageTk
import os

from app.utils.icon import set_app_icon
from app.utils.lang import t


def _face_name(slot_id: str) -> str:
    return t(f"character_editor.face_slots.{slot_id}", **{}) if t(f"character_editor.face_slots.{slot_id}") != f"character_editor.face_slots.{slot_id}" else slot_id


class CharacterEditorUI(ctk.CTkToplevel):
    
    def __init__(self, parent, is_secondary=False, on_open_in_editor_callback=None, from_patch=False):
        super().__init__(parent)
        
        self.parent = parent
        self.is_secondary = is_secondary
        self.from_patch = from_patch
        self.on_open_in_editor_callback = on_open_in_editor_callback
        # Modo limitado: solo muestra botones de abrir en editor + exportar textura
        self._limited_mode = is_secondary or from_patch
        
        # Importar después de crear la ventana
        from app.logic_patch import CharacterAnalyzer
        
        self.analyzer = CharacterAnalyzer()
        self.texture_image = None
        self.current_ctk_image = None
        
        # Configuración de ventana
        title_text = t("character_editor.titulo_sec") if is_secondary else t("character_editor.titulo")
        self.title(title_text)
        self.geometry("700x700")
        self.minsize(600, 600)
        
        set_app_icon(self)
        
        self.transient(parent)
        self.grab_set()
        
        # Centrar ventana
        from app.utils import center_window
        self.after(10, lambda: center_window(self, 700, 700))
        
        self.setup_ui()
    
    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        load_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        load_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 10))

        # "Abrir Personaje" solo en modo completo
        if not self._limited_mode:
            self.load_btn = ctk.CTkButton(
                load_frame,
                text=t("character_editor.btn_abrir_personaje"),
                command=self.load_character,
                height=40,
                font=("Segoe UI", 14, "bold"),
                corner_radius=8,
                fg_color=("#2196F3", "#1976D2"),
                hover_color=("#1976D2", "#1565C0")
            )
            self.load_btn.pack(fill="x")

        # "Abrir PMDL en el Editor" siempre que haya callback
        if self.on_open_in_editor_callback:
            self.open_in_editor_btn = ctk.CTkButton(
                load_frame,
                text=t("character_editor.btn_abrir_pmdl_editor"),
                command=self._on_open_in_editor,
                height=40,
                font=("Segoe UI", 14, "bold"),
                corner_radius=8,
                state="disabled",
                fg_color=("#FF9800", "#F57C00"),
                hover_color=("#F57C00", "#E65100")
            )
            top_pad = 0 if self._limited_mode else 10
            self.open_in_editor_btn.pack(fill="x", pady=(top_pad, 0))

            self.faces_frame = ctk.CTkFrame(load_frame, fg_color="transparent")

            self.open_face_btn = ctk.CTkButton(
                self.faces_frame,
                text=t("character_editor.btn_abrir_pmdf_editor"),
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
                values=[_face_name("Cara_damage")],
                height=38,
                font=("Segoe UI", 12),
                corner_radius=8,
                fg_color=("#673AB7", "#512DA8"),
                button_color=("#512DA8", "#4527A0"),
                button_hover_color=("#4527A0", "#311B92")
            )
            self.face_dropdown.pack(side="right", padx=0)

        # Área de textura
        texture_container = ctk.CTkFrame(main_frame, corner_radius=12)
        texture_container.grid(row=2, column=0, sticky="nsew", padx=30, pady=(10, 20))
        texture_container.grid_rowconfigure(1, weight=1)
        texture_container.grid_columnconfigure(0, weight=1)

        tex_header = ctk.CTkFrame(texture_container, fg_color="transparent", height=40)
        tex_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))

        ctk.CTkLabel(
            tex_header,
            text=t("character_editor.textura_personaje"),
            font=("Segoe UI", 11, "bold")
        ).pack(side="left")

        self.texture_info_label = ctk.CTkLabel(
            tex_header,
            text="",
            font=("Segoe UI", 10),
            text_color=("gray50", "gray50")
        )
        self.texture_info_label.pack(side="right")

        self.texture_frame = ctk.CTkFrame(texture_container, fg_color="transparent")
        self.texture_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=(5, 15))
        self.texture_frame.grid_rowconfigure(0, weight=1)
        self.texture_frame.grid_columnconfigure(0, weight=1)

        self.texture_label = ctk.CTkLabel(
            self.texture_frame,
            text=t("character_editor.no_textura"),
            font=("Segoe UI", 12),
            text_color=("gray50", "gray50")
        )
        self.texture_label.grid(row=0, column=0)

        # Menú contextual con tema oscuro
        self.texture_menu = Menu(
            self, tearoff=0,
            bg="#2b2b2b", fg="white",
            activebackground="#3c3c3c", activeforeground="white",
            font=("Segoe UI", 13),
            bd=0, relief="flat",
            activeborderwidth=0
        )
        if not self._limited_mode:
            self.texture_menu.add_command(
                label=f"  📥  {t('character_editor.menu_importar_png')}",
                command=self.import_texture_dialog
            )
            self.texture_menu.add_command(
                label=f"  📥  {t('character_editor.menu_importar_raw')}",
                command=self.import_texture_raw_dialog
            )
            self.texture_menu.add_separator()
        self.texture_menu.add_command(
            label=f"  📤  {t('character_editor.menu_exportar_png')}",
            command=self.export_texture_dialog
        )
        self.texture_menu.add_command(
            label=f"  📤  {t('character_editor.menu_exportar_raw')}",
            command=self.export_texture_raw_dialog
        )

        self.texture_label.bind("<Button-3>", self.show_texture_menu)

        # Sección PMDF y botones de acción: solo en modo completo
        if not self._limited_mode:
            pmdf_container = ctk.CTkFrame(main_frame, corner_radius=10)
            pmdf_container.grid(row=3, column=0, sticky="ew", padx=30, pady=(0, 10))
            pmdf_container.grid_columnconfigure(0, weight=1)

            pmdf_header = ctk.CTkFrame(pmdf_container, fg_color="transparent")
            pmdf_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 4))

            ctk.CTkLabel(
                pmdf_header,
                text=t("character_editor.caras_extra"),
                font=("Segoe UI", 13, "bold"),
            ).pack(side="left")

            pmdf_row = ctk.CTkFrame(pmdf_container, fg_color="transparent")
            pmdf_row.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 12))
            pmdf_row.grid_columnconfigure(0, weight=1)

            self.pmdf_slot_dropdown = ctk.CTkOptionMenu(
                pmdf_row,
                values=[t("character_editor.carga_primero")],
                height=36,
                font=("Segoe UI", 12),
                corner_radius=8,
                fg_color=("#3a3a3a", "#2a2a2a"),
                button_color=("#555555", "#444444"),
                button_hover_color=("#666666", "#555555"),
                state="disabled",
            )
            self.pmdf_slot_dropdown.grid(row=0, column=0, sticky="ew", padx=(0, 8))

            self.import_pmdf_btn = ctk.CTkButton(
                pmdf_row,
                text=t("character_editor.btn_importar_pmdf"),
                command=self.import_pmdf_dialog,
                height=36,
                width=140,
                font=("Segoe UI", 12, "bold"),
                state="disabled",
                corner_radius=8,
                fg_color=("#5C35A0", "#4A2880"),
                hover_color=("#4A2880", "#3A1E65"),
            )
            self.import_pmdf_btn.grid(row=0, column=1, sticky="e", padx=(0, 6))

            self.delete_pmdf_btn = ctk.CTkButton(
                pmdf_row,
                text=t("character_editor.btn_eliminar"),
                command=self.delete_pmdf_dialog,
                height=36,
                width=100,
                font=("Segoe UI", 12, "bold"),
                state="disabled",
                corner_radius=8,
                fg_color=("#8B1A1A", "#6B1212"),
                hover_color=("#6B1212", "#4A0D0D"),
            )
            self.delete_pmdf_btn.grid(row=0, column=2, sticky="e")

            actions_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            actions_frame.grid(row=4, column=0, sticky="ew", padx=30, pady=(0, 30))
            actions_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

            self.export_pmdl_btn = ctk.CTkButton(
                actions_frame,
                text=t("character_editor.btn_exportar_pmdl"),
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
                text=t("character_editor.btn_importar_pmdl"),
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
                text=t("character_editor.btn_guardar"),
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
                text=t("character_editor.btn_guardar_como"),
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
            title="Abrir archivo de personaje",
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
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.personaje_cargado", name=os.path.basename(file_path)))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_no_pmdl_textura"))
        else:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_cargar_archivo"))
    
    def load_character_from_path(self, file_path):
        """Carga un personaje desde una ruta específica (usado por el controlador)."""
        if self.analyzer.load_file(file_path):
            if self.analyzer.find_pmdl_and_texture():
                self.display_texture()
                self.enable_buttons()
                return True
        return False
    
    def display_texture(self):
        img = self.analyzer.generate_texture_image()
        if img:
            orig_w, orig_h = img.width, img.height

            # Modo limitado: imagen 40% más grande (392px vs 280px)
            display_size = 392 if self._limited_mode else 280
            scale = min(display_size / img.width, display_size / img.height)
            new_w = max(1, int(img.width * scale))
            new_h = max(1, int(img.height * scale))
            resample = Image.Resampling.LANCZOS if self._limited_mode else Image.Resampling.NEAREST
            img = img.resize((new_w, new_h), resample)

            self.current_ctk_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(new_w, new_h)
            )

            self.texture_label.configure(image=self.current_ctk_image, text="")
            self.texture_image = img

            if self.analyzer.texture_info:
                size_kb = self.analyzer.texture_info['size'] / 1024
                self.texture_info_label.configure(
                    text=f"{orig_w}x{orig_h} • {size_kb:.1f} KB"
                )
        else:
            self.texture_label.configure(image="", text=t("character_editor.error_textura"))

    def enable_buttons(self):
        if hasattr(self, 'open_in_editor_btn'):
            self.open_in_editor_btn.configure(state="normal")

        is_wrapper = isinstance(self.analyzer, FaceAnalyzerWrapper)

        if not is_wrapper and hasattr(self, 'on_open_in_editor_callback') and self.on_open_in_editor_callback:
            self._detect_and_show_extra_faces()

        if not self._limited_mode:
            self.export_pmdl_btn.configure(state="normal")
            self.import_pmdl_btn.configure(state="normal")
            self.save_btn.configure(state="normal")
            self.save_as_btn.configure(state="normal")

        if not is_wrapper and hasattr(self, 'pmdf_slot_dropdown'):
            self._refresh_pmdf_dropdown()
    
    def _detect_and_show_extra_faces(self):
        """Detecta caras extra y muestra el botón + dropdown si existen."""
        faces = self.analyzer.find_extra_faces()
        
        if faces:
            face_names = list(faces.keys())
            translated = [_face_name(n) for n in face_names]
            self._face_name_map = dict(zip(translated, face_names))
            self.face_dropdown.configure(values=translated)
            self.face_dropdown.set(translated[0])
            
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
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.no_textura_cargada"))
            return
        
        file_path = filedialog.asksaveasfilename(
            title=t("character_editor.exportar_textura"),
            defaultextension=".png",
            filetypes=[("Imágenes PNG", "*.png")]
        )
        
        if file_path:
            if self.analyzer.export_texture(file_path):
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.textura_exportada", path=file_path))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_exportar_textura"))
    
    def import_texture_dialog(self):
        if not self.analyzer.texture_info:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.carga_personaje_primero"))
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar textura",
            filetypes=[("Imágenes PNG", "*.png")]
        )
        
        if file_path:
            if self.analyzer.import_texture(file_path):
                self.display_texture()
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.textura_importada"))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_importar_textura"))

    def export_texture_raw_dialog(self):
        """Exporta la textura en formato RAW (bytes crudos del parche)."""
        if not self.analyzer.texture_info:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.no_textura_cargada"))
            return

        file_path = filedialog.asksaveasfilename(
            title="Exportar Textura RAW",
            defaultextension=".atex",
            filetypes=[("Textura ATEX", "*.atex"), ("Archivo UNK", "*.unk"), ("Todos", "*.*")]
        )
        if not file_path:
            return

        try:
            start = self.analyzer.texture_info['start']
            end   = self.analyzer.texture_info['end']
            with open(file_path, 'wb') as f:
                f.write(self.analyzer.file_data[start:end])
            messagebox.showinfo(t("character_editor.exito"), t("character_editor.textura_raw_exportada", path=file_path))
        except Exception as e:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_exportar_raw", e=e))

    def import_texture_raw_dialog(self):
        """Importa una textura en formato RAW (reemplaza bytes crudos en el parche)."""
        if not self.analyzer.texture_info:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.carga_personaje_primero"))
            return

        file_path = filedialog.askopenfilename(
            title="Importar Textura RAW",
            filetypes=[("Textura ATEX", "*.atex"), ("Archivo UNK", "*.unk"), ("Todos", "*.*")]
        )
        if not file_path:
            return

        if self.analyzer.import_texture(file_path):
            self.display_texture()
            messagebox.showinfo(t("character_editor.exito"), t("character_editor.textura_raw_importada"))
        else:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_importar_raw"))

    def export_pmdl_dialog(self):
        """Exporta el pMdl a un archivo."""
        if not self.analyzer.pmdl_info:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.no_pmdl_cargado"))
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Exportar pMdl",
            defaultextension=".pmdl",
            filetypes=[("Archivos PMDL", "*.pmdl")]
        )
        
        if file_path:
            if self.analyzer.export_pmdl(file_path):
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.pmdl_exportado", path=file_path))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_exportar_pmdl"))
    
    def import_pmdl_dialog(self):
        """Importa un pMdl desde un archivo."""
        if not self.analyzer.pmdl_info:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.carga_personaje_primero"))
            return
        
        file_path = filedialog.askopenfilename(
            title="Importar pMdl",
            filetypes=[("Archivos PMDL", "*.pmdl")]
        )
        
        if file_path:
            if self.analyzer.import_pmdl(file_path):
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.pmdl_importado"))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_importar_pmdl"))
    
    def save_character(self):
        """Guarda el personaje en el archivo original."""
        if not self.analyzer.file_path:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.no_archivo_cargado"))
            return
        
        if messagebox.askyesno(t("character_editor.confirmar"), t("character_editor.confirmar_guardar")):
            if self.analyzer.save_file():
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.personaje_guardado"))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_guardar_archivo"))
    
    def save_character_as(self):
        """Guarda el personaje en un nuevo archivo."""
        file_path = filedialog.asksaveasfilename(
            title="Guardar personaje como",
            defaultextension=".PCK1",
            filetypes=[("Archivos PCK1", "*.PCK1"), ("Archivos PAK", "*.pak")]
        )
        
        if file_path:
            if self.analyzer.save_file(file_path):
                messagebox.showinfo(t("character_editor.exito"), t("character_editor.personaje_guardado_en", path=file_path))
            else:
                messagebox.showerror(t("character_editor.error"), t("character_editor.error_guardar_archivo"))
    
    def _on_open_in_editor(self):
        """Callback para abrir el PMDL en el editor principal."""
        if self.on_open_in_editor_callback and self.analyzer.pmdl_info:
            self.on_open_in_editor_callback(self.analyzer)
    
    def _on_open_face_in_editor(self):
        """Callback para abrir un PMDF (cara extra) en el editor principal."""
        if not self.on_open_in_editor_callback:
            return
        
        # Obtener cara seleccionada
        selected_label = self.face_dropdown.get()
        selected_face = getattr(self, '_face_name_map', {}).get(selected_label, selected_label)

        faces = self.analyzer.find_extra_faces()
        if selected_face not in faces:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_cara_no_encontrada", name=selected_face))
            return
        
        face_analyzer = FaceAnalyzerWrapper(self.analyzer, selected_face)
        
        # Llamar al callback con el wrapper
        self.on_open_in_editor_callback(face_analyzer)
    
    def _refresh_pmdf_dropdown(self):
        """Rellena el dropdown de slots PMDF con el estado actual (vacío o con datos)."""
        if not hasattr(self, 'pmdf_slot_dropdown'):
            return
        
        slots = self.analyzer.get_all_face_slots()
        if not slots:
            return
        
        labels = []
        for s in slots:
            name_translated = _face_name(s['name'])
            if s['empty']:
                labels.append(f"{name_translated} ({t('character_editor.slot_vacio')})")
            else:
                labels.append(name_translated)
        
        self._slot_label_map = {}
        for s, label in zip(slots, labels):
            self._slot_label_map[label] = s['name']
        
        self.pmdf_slot_dropdown.configure(
            values=labels,
            state="normal",
            command=self._on_pmdf_slot_changed
        )
        self.pmdf_slot_dropdown.set(labels[0])
        self.import_pmdf_btn.configure(state="normal")
        # Estado del botón eliminar según el primer slot
        self._update_delete_btn_state(labels[0])

    def _on_pmdf_slot_changed(self, selected_label):
        """Actualiza el estado del botón eliminar según el slot seleccionado."""
        self._update_delete_btn_state(selected_label)

    def _update_delete_btn_state(self, label):
        """Habilita Eliminar solo si el slot tiene datos (no es Vacío)."""
        if not hasattr(self, 'delete_pmdf_btn'):
            return
        is_empty = label.endswith(f"({t('character_editor.slot_vacio')})")
        self.delete_pmdf_btn.configure(state="disabled" if is_empty else "normal")

    def import_pmdf_dialog(self):
        """Abre el explorador y reemplaza/inserta el PMDF en el slot seleccionado."""
        if not self.analyzer.file_data:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.carga_personaje_primero"))
            return
        
        selected_label = self.pmdf_slot_dropdown.get()
        slot_name = getattr(self, '_slot_label_map', {}).get(selected_label, selected_label.split(" (")[0])
        
        file_path = filedialog.askopenfilename(
            title=f"Importar PMDF para slot: {slot_name}",
            filetypes=[
                ("Archivos PMDL/PMDF", "*.pmdl *.pmdf"),
                ("Archivos Unknown", "*.unk"),
                ("Todos", "*.*")
            ]
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'rb') as f:
                face_data = f.read()
        except Exception as e:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_leer_archivo", e=e))
            return
        
        # Validar firma
        if face_data[:4] not in (b'pMdl', b'pMdF'):
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_firma_invalida"))
            return
        
        if self.analyzer.insert_face_data(slot_name, bytearray(face_data)):
            messagebox.showinfo(t("character_editor.exito"), t("character_editor.pmdf_importado_msg", slot=slot_name))
            self._refresh_pmdf_dropdown()
            if hasattr(self, 'faces_frame'):
                self._detect_and_show_extra_faces()
                if hasattr(self, 'face_dropdown'):
                    current_values = self.face_dropdown.cget("values")
                    translated_slot = _face_name(slot_name)
                    if translated_slot in current_values:
                        self.face_dropdown.set(translated_slot)
        else:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_insertar_pmdf", slot=slot_name))

    def delete_pmdf_dialog(self):
        """Elimina el PMDF del slot seleccionado, dejándolo vacío."""
        if not self.analyzer.file_data:
            messagebox.showwarning(t("character_editor.advertencia"), t("character_editor.carga_personaje_primero"))
            return
        
        selected_label = self.pmdf_slot_dropdown.get()
        slot_name = getattr(self, '_slot_label_map', {}).get(selected_label, selected_label.split(" (")[0])
        
        if not messagebox.askyesno(
            t("character_editor.confirmar_eliminacion"),
            t("character_editor.confirmar_eliminar_pmdf", slot=slot_name)
        ):
            return
        
        if self.analyzer.delete_face_data(slot_name):
            messagebox.showinfo(t("character_editor.exito"), t("character_editor.pmdf_eliminado", slot=slot_name))
            self._refresh_pmdf_dropdown()
            if hasattr(self, 'faces_frame'):
                self._detect_and_show_extra_faces()
        else:
            messagebox.showerror(t("character_editor.error"), t("character_editor.error_eliminar_pmdf", slot=slot_name))

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