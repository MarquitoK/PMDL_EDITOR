import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import Optional, List

from app.binary_builder.pross_data import AppPortador
from app.core import (
    PmdlHeader, parse_header,
    PartIndexEntry, parse_parts_index,
    FLAG_MAP_LABEL_TO_VALUE,
    export_part, delete_part, import_part,
    add_part_from_secondary, sync_parts_from_ui
)
from app.ui import build_main_layout
from app.ui.menubar import MenuBar
from app.ui.about_window import AboutWindow
from app.utils import center_window
from app.utils.thickness_normalizer import leer_grosor, normalizar_pmdl_completo, preparar_parte_externa_para_insercion
from app.utils.part_header import exportar_parte_con_encabezado, importar_parte_con_encabezado
from app.logic_sub_parts_pmdl.ui_pmdl_sub_parts import UiSubparts
from app.logic_patch import PatchBridge, CharacterEditorUI
from app.logic_3d.main_window import PMDLViewerApp
from app.utils.ui_error_window import error_window_ui

APP_TITLE = "Pmdl Editor (TTT) · By Los ijue30s · v1.4.2"
GEOMETRY = (1070, 600)


class PmdlPartsApp(ctk.CTk):
    """Aplicación principal del editor de PMDL."""
    
    def __init__(self):
        super().__init__()
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.title(APP_TITLE)
        self.geometry(f"{GEOMETRY[0]}x{GEOMETRY[1]}")
        self.minsize(540, 540)
        
        # Centrar ventana
        center_window(self, GEOMETRY[0], GEOMETRY[1])
        
        # Interceptar cierre de la ventana
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Estado del PMDL Principal
        self._blob: Optional[bytearray] = None
        self._hdr: Optional[PmdlHeader] = None
        self._parts: List[PartIndexEntry] = []
        self._path: Optional[str] = None
        
        # Estado del PMDL secundario
        self._blob2: Optional[bytearray] = None
        self._hdr2: Optional[PmdlHeader] = None
        self._parts2: List[PartIndexEntry] = []
        self._path2: Optional[str] = None
        
        # Estado de normalización de grosor
        self.normalize_thickness_enabled = True
        
        # Construir menu bar
        self._build_menubar()
        
        # Construir UI
        callbacks = {
            'on_part_depth_changed': self.on_part_depth_changed,
            'on_part_opacity_changed': self.on_part_opacity_changed,
            'on_part_flag_changed': self.on_part_flag_changed,
            'on_export_part': self.on_export_part,
            'on_delete_part': self.on_delete_part,
            'on_add_part_from_secondary': self.on_add_part_from_secondary,
        }
        
        widgets = build_main_layout(self, callbacks)
        
        # Referencias a widgets
        self.path_entry = widgets['path_entry']
        self.tooltip_path_entry = widgets['tooltip_path_entry']
        self.path2_entry = widgets['path2_entry']
        self.tooltip_path2_entry = widgets['tooltip_path2_entry']
        self.parts_table = widgets['parts_table']
        self.parts2_table = widgets['parts2_table']
        self.status_var = widgets['status_var']
        self.normalize_toggle = widgets.get('normalize_toggle')
        self.normalize_toggle_var = widgets.get('normalize_toggle_var')

        # Referencia para la ventana de subparts
        self.window_subparts = None
        
        # Referencia para la ventana de character editor
        self.window_character_editor = None
        
        # Referencia para la ventana de vista 3D
        self.window_viewer_3d = None
        
        # Puente para manejo de parches
        self.patch_bridge = PatchBridge()
        
        # Puente para manejo de parches secundarios
        self.patch_bridge_secondary = PatchBridge()
        
        # Configurar shortcuts de teclado
        self._bind_keyboard_shortcuts()
    
    def _build_menubar(self):
        """Construye el menu bar de la aplicación."""
        self.menubar = MenuBar(self, height=28)
        self.menubar.pack(side="top", fill="x", pady=(0, 0))
        
        # Menú Archivo
        menu_archivo = self.menubar.add_menu("Archivo")
        menu_archivo.add_command("Abrir PMDL", self.on_open_file, "Ctrl+O")
        menu_archivo.add_command("Abrir Parche", self.on_open_patch, "Ctrl+P")
        menu_archivo.add_separator()
        menu_archivo.add_command("Guardar", self.on_save, "Ctrl+S")
        menu_archivo.add_command("Guardar Como", self.on_save_as, "Ctrl+Shift+S")
        
        # Menú Tools
        menu_tools = self.menubar.add_menu("Tools")
        menu_tools.add_command("Character Editor", self.on_open_character_editor, "Ctrl+R")
        menu_tools.add_command("SubParts Editor", self.on_open_subparts_editor, "Ctrl+T")
        menu_tools.add_command("Vista 3D", self.on_open_3d_viewer, "Ctrl+D")
        
        # Menú Opciones
        menu_opciones = self.menubar.add_menu("Opciones")
        # Aquí pondré algunos ajustes a futuro pero aun no quiero entrar en eso xD
        menu_opciones.add_command("Convertir JSON a TTTPART", self.on_convert_json_to_tttpart)
        
        # Botón Acerca De
        acerca_btn = ctk.CTkButton(
            self.menubar,
            text="Acerca De",
            width=75,
            height=22,
            corner_radius=3,
            font=("Segoe UI", 11),
            fg_color="transparent",
            hover_color=("gray75", "gray25"),
            command=self.on_show_about
        )
        acerca_btn.pack(side="left", padx=1, pady=1)
        
        # Separador
        separator = ctk.CTkFrame(self.menubar, width=200, fg_color="transparent")
        separator.pack(side="left", fill="x", expand=True)
        
        # Menú Archivo Secundario
        menu_archivo_sec = self.menubar.add_menu("Archivo Secundario")
        menu_archivo_sec.add_command("Abrir PMDL Secundario", self.on_open_file_secondary, "Ctrl+Shift+O")
        menu_archivo_sec.add_command("Abrir Parche Secundario", self.on_open_patch_secondary, "Ctrl+Shift+P")
        menu_archivo_sec.add_command("Visualizar", self.on_visualize_secondary, "Ctrl+Shift+D")
    
    def _bind_keyboard_shortcuts(self):
        """Configura los atajos de teclado."""
        # Archivo Principal
        self.bind("<Control-o>", lambda e: self.on_open_file())
        self.bind("<Control-O>", lambda e: self.on_open_file())
        
        self.bind("<Control-p>", lambda e: self.on_open_patch())
        self.bind("<Control-P>", lambda e: self.on_open_patch())
        
        self.bind("<Control-s>", lambda e: self.on_save())
        self.bind("<Control-S>", lambda e: self.on_save())
        
        self.bind("<Control-Shift-S>", lambda e: self.on_save_as())
        self.bind("<Control-Shift-s>", lambda e: self.on_save_as())
        
        # Tools
        self.bind("<Control-t>", lambda e: self.on_open_subparts_editor())
        self.bind("<Control-T>", lambda e: self.on_open_subparts_editor())
        
        self.bind("<Control-d>", lambda e: self.on_open_3d_viewer())
        self.bind("<Control-D>", lambda e: self.on_open_3d_viewer())
        
        self.bind("<Control-r>", lambda e: self.on_open_character_editor())
        self.bind("<Control-R>", lambda e: self.on_open_character_editor())
        
        # Archivo Secundario
        self.bind("<Control-Shift-O>", lambda e: self.on_open_file_secondary())
        self.bind("<Control-Shift-o>", lambda e: self.on_open_file_secondary())
        
        self.bind("<Control-Shift-P>", lambda e: self.on_open_patch_secondary())
        self.bind("<Control-Shift-p>", lambda e: self.on_open_patch_secondary())
        
        self.bind("<Control-Shift-D>", lambda e: self.on_visualize_secondary())
        self.bind("<Control-Shift-d>", lambda e: self.on_visualize_secondary())
        
        # Importar Parte
        self.bind("<Control-i>", lambda e: self.on_import_part() if self._blob else None)
        self.bind("<Control-I>", lambda e: self.on_import_part() if self._blob else None)
    
    def on_close(self):
        """Confirmación antes de cerrar la aplicación."""
        if messagebox.askyesno("Salir", "¿Estas seguro de que deseas cerrar la aplicacion?"):
            self.destroy()
    
    def on_show_about(self):
        """Muestra la ventana Acerca de."""
        AboutWindow(self)

    @error_window_ui
    def on_open_subparts_editor(self):
        """Abre el editor de SubParts con intercambio de ventanas."""
        # Validación previa: verificar que al menos un archivo esté cargado
        if not self._path and not self._path2:
            messagebox.showinfo("Información", "Abre al menos un archivo para editar")
            return

        self.withdraw()

        if self.window_subparts is None or not self.window_subparts.winfo_exists():
            # Crear ventana de subparts
            self.window_subparts = UiSubparts(self)

            # Bind para volver con ESC
            self.window_subparts.bind("<Escape>", lambda e: self._return_from_subparts())

            # Bind para cuando se cierre la ventana
            self.window_subparts.protocol("WM_DELETE_WINDOW", self._return_from_subparts)

            # Cargar subparts en la UI automáticamente
            self.window_subparts.get_data_subpart()
            self.window_subparts.get_data_subpart(1)
        else:
            # Si ya existe, traerla al frente
            self.window_subparts.focus()
            self.window_subparts.lift()

    def on_open_pmdl_editor(self):
        """Mostrar el editor PMDL."""
        self.deiconify()

    
    def _return_from_subparts(self):
        # Cierra subparts y regresa a la ventana principal
        if self.window_subparts and self.window_subparts.winfo_exists():
            # necesario usar al regresar a la ventana principal
            self.window_subparts.on_back()
        self.window_subparts = None
        
        # Mostrar ventana principal
        self.deiconify()
        self.focus_force()

    @error_window_ui
    def on_convert_json_to_tttpart(self):
        AppPortador(self)

    def on_open_3d_viewer(self):
        """Abre el visor 3D con intercambio de ventanas."""
        if self.window_viewer_3d is None or not self.window_viewer_3d.winfo_exists():
            # Preparar datos
            pmdl_data = None
            texture_path = None
            
            # Si hay PMDL principal cargado
            if self._blob:
                try:
                    # Sincronizar datos de UI a memoria antes de abrir el visor
                    ui_data = self.parts_table.get_ui_data()
                    sync_parts_from_ui(self._blob, self._hdr, self._parts, ui_data)
                    
                    pmdl_data = bytes(self._blob)
                    
                    # Si viene de parche, extraer textura
                    if self.patch_bridge.is_from_patch():
                        analyzer = self.patch_bridge.get_patch_analyzer()
                        if analyzer and analyzer.texture_info:
                            import tempfile
                            try:
                                img = analyzer.generate_texture_image()
                                if img:
                                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp:
                                        img.save(tmp.name)
                                        texture_path = tmp.name
                            except Exception as e:
                                print(f"Error extrayendo textura: {e}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo preparar los datos del modelo:\n{e}")
                    self.deiconify()
                    return
            
            self.withdraw()
            
            try:
                # Crear ventana del visor 3D
                self.window_viewer_3d = PMDLViewerApp(self, pmdl_data, texture_path)
                
                # Bind para cerrar con ESC
                self.window_viewer_3d.bind("<Escape>", lambda e: self._return_from_3d_viewer())
                
                # Bind para cuando se cierre con X
                self.window_viewer_3d.protocol("WM_DELETE_WINDOW", self._return_from_3d_viewer)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el visor 3D:\n{e}")
                self.deiconify()
        else:
            self.window_viewer_3d.focus()
            self.window_viewer_3d.lift()
    
    def _return_from_3d_viewer(self):
        # Cierra el visor 3D y regresa a la ventana principal
        if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
            if hasattr(self.window_viewer_3d, 'has_unsaved_changes') and self.window_viewer_3d.has_unsaved_changes:
                modified_pmdl = self.window_viewer_3d.get_modified_pmdl_data()
                if modified_pmdl:
                    # Actualizar el blob con los cambios de UVs
                    self._blob = bytearray(modified_pmdl)
                    
                    # Si viene de parche, guardar automáticamente
                    if self.patch_bridge.is_from_patch():
                        try:
                            analyzer = self.patch_bridge.get_patch_analyzer()
                            if analyzer:
                                # CharacterAnalyzer guarda datos en analyzer.character_data
                                if hasattr(analyzer, 'character_data'):
                                    analyzer.character_data['pmdl_blob'] = bytes(self._blob)
                                    analyzer.save_patch()
                                    print("✓ Cambios de UVs guardados en el parche automáticamente")
                                else:
                                    print("Advertencia: No se pudo guardar automáticamente en el parche")
                        except Exception as e:
                            print(f"Error al guardar cambios de UVs en parche: {e}")
                    else:
                        print("✓ Cambios de UVs aplicados")
                    
                    # Re-analizar el PMDL actualizado
                    try:
                        from app.core import parse_header, parse_parts_index
                        
                        self._hdr = parse_header(self._blob)
                        self._parts = parse_parts_index(self._blob, self._hdr)
                        
                        # Actualizar tabla
                        if hasattr(self, 'parts_table'):
                            self.parts_table.populate(self._parts)
                            self.parts_table.update_part_count(self._hdr.part_count)
                    except Exception as e:
                        print(f"Error al re-analizar PMDL: {e}")
            
            self.window_viewer_3d.cleanup()
            self.window_viewer_3d.destroy()
        self.window_viewer_3d = None
        
        # Mostrar ventana principal
        self.deiconify()
        self.focus_force()
    
    def on_open_character_editor(self):
        # Abre el Character Editor como sub-herramienta
        if self.window_character_editor is None or not self.window_character_editor.winfo_exists():
            # Ocultar ventana principal
            self.withdraw()
            
            # Abrir Character Editor
            self.window_character_editor = CharacterEditorUI(
                self,
                is_secondary=False,
                on_open_in_editor_callback=self._on_load_pmdl_from_patch
            )
            
            if self.patch_bridge.is_from_patch():
                analyzer = self.patch_bridge.get_patch_analyzer()
                patch_path = self.patch_bridge.get_patch_path()
                
                if analyzer and patch_path:
                    # Cargar el parche en el Character Editor
                    if self.window_character_editor.load_character_from_path(patch_path):
                        pass
            
            # Bind para cerrar con ESC
            self.window_character_editor.bind("<Escape>", lambda e: self._return_from_character_editor())
            
            # Bind para cuando se cierre con X
            self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_from_character_editor)
        else:
            self.window_character_editor.focus()
            self.window_character_editor.lift()
        self.focus()
        self.lift()
    
    def _on_load_pmdl_from_patch(self, analyzer):
        # Extraer PMDL del parche
        pmdl_data = self.patch_bridge.extract_pmdl_from_patch(analyzer)
        
        if not pmdl_data:
            messagebox.showerror("Error", "No se pudo extraer el PMDL del parche")
            return
        
        # Guardar contexto del parche
        patch_path = analyzer.file_path
        self.patch_bridge.set_patch_context(patch_path, analyzer, is_secondary=False)
        
        self._return_from_character_editor()
        
        # Cargar PMDL en el editor principal
        try:
            hdr = parse_header(pmdl_data)
            parts = parse_parts_index(pmdl_data, hdr)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo parsear el PMDL:\n{e}")
            self.patch_bridge.clear_patch_context()
            return
        
        self._blob = pmdl_data
        self._hdr = hdr
        self._parts = parts
        self._path = f"[PATCH]{patch_path}"
        
        # Actualizar UI
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, f"[Parche] {os.path.basename(patch_path)}")
        self.path_entry.configure(state="disabled")
        self.tooltip_path_entry.change_text(f"PMDL extraído de: {patch_path}")
        
        # Poblar tabla
        self.parts_table.show_top_controls(self._hdr.part_count, self.on_import_part)
        self.parts_table.populate(self._parts)
        
        self.status_var.set(f"PMDL cargado desde parche: {os.path.basename(patch_path)} · Los ijue30s")
    
    def _on_load_pmdl_from_patch_secondary(self, analyzer):
        # Extraer PMDL del parche
        pmdl_data = self.patch_bridge_secondary.extract_pmdl_from_patch(analyzer)
        
        if not pmdl_data:
            messagebox.showerror("Error", "No se pudo extraer el PMDL del parche secundario")
            return
        
        # Guardar contexto del parche secundario
        patch_path = analyzer.file_path
        self.patch_bridge_secondary.set_patch_context(patch_path, analyzer, is_secondary=True)
        
        # Cerrar Character Editor
        self._return_from_character_editor()
        
        # Cargar PMDL como secundario
        try:
            hdr = parse_header(pmdl_data)
            parts = parse_parts_index(pmdl_data, hdr)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo parsear el PMDL:\n{e}")
            self.patch_bridge_secondary.clear_patch_context()
            return
        
        self._blob2 = pmdl_data
        self._hdr2 = hdr
        self._parts2 = parts
        self._path2 = patch_path
        
        # Actualizar UI
        self.path2_entry.configure(state="normal")
        self.path2_entry.delete(0, tk.END)
        self.path2_entry.insert(0, f"[Parche] {os.path.basename(patch_path)}")
        self.path2_entry.configure(state="disabled")
        self.tooltip_path2_entry.change_text(f"PMDL extraído de: {patch_path}")
        
        # Poblar tabla
        self.parts2_table.show_top_controls(self._hdr2.part_count)
        self.parts2_table.populate(self._parts2)
        
        self.status_var.set(f"PMDL secundario cargado desde parche: {os.path.basename(patch_path)} · Los ijue30s")
    
    def _return_from_character_editor(self):
        """Cierra Character Editor y regresa a la ventana principal."""
        if self.window_character_editor and self.window_character_editor.winfo_exists():
            self.window_character_editor.destroy()
        self.window_character_editor = None
        
        # Mostrar ventana principal
        self.deiconify()
        self.focus_force()
    
    def on_open_patch(self):
        """Abre un parche principal en el Character Editor."""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo de parche",
            filetypes=[
                ("Archivos de personaje", "*.PCK1 *.pak"),
                ("Todos los archivos", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        # Ocultar ventana principal
        self.withdraw()
        
        # Abrir Character Editor
        self.window_character_editor = CharacterEditorUI(
            self,
            is_secondary=False,
            on_open_in_editor_callback=self._on_load_pmdl_from_patch
        )
        
        # Bind para volver con ESC
        self.window_character_editor.bind("<Escape>", lambda e: self._return_from_character_editor())
        
        # Bind para cuando se cierre la ventana
        self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_from_character_editor)
        
        # Cargar parche automáticamente
        if not self.window_character_editor.load_character_from_path(file_path):
            messagebox.showerror("Error", "No se pudo cargar el parche")
            self._return_from_character_editor()

    @error_window_ui
    def on_open_patch_secondary(self):
        """Abre un parche secundario en el Character Editor (modo solo lectura)."""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo de parche secundario",
            filetypes=[
                ("Archivos de personaje", "*.PCK1 *.pak"),
                ("Todos los archivos", "*.*")
            ]
        )

        if not file_path:
            return
        
        # Ocultar ventana principal
        self.withdraw()
        
        # Abrir Character Editor (modo secundario)
        self.window_character_editor = CharacterEditorUI(
            self,
            is_secondary=True,
            on_open_in_editor_callback=self._on_load_pmdl_from_patch_secondary
        )
        
        # Bind para volver con ESC
        self.window_character_editor.bind("<Escape>", lambda e: self._return_from_character_editor())
        
        # Bind para cuando se cierre la ventana
        self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_from_character_editor)
        
        # Cargar parche automáticamente
        if not self.window_character_editor.load_character_from_path(file_path):
            messagebox.showerror("Error", "No se pudo cargar el parche secundario")
            self._return_from_character_editor()

    def on_visualize_secondary(self):
        """Abre el visualizador 3D con el PMDL secundario."""
        if self._blob2 is None or self._hdr2 is None or not self._parts2:
            messagebox.showinfo("Info", "Abre primero un PMDL secundario.")
            return
        
        # Preparar datos del PMDL secundario
        pmdl_data = bytes(self._blob2)
        texture_path = None
        
        # Si el secundario viene de parche, extraer textura
        if self.patch_bridge_secondary.is_from_patch():
            texture_path = self.patch_bridge_secondary.extract_texture_temp()
        
        self.withdraw()
        
        try:
            # Crear ventana del visor 3D con PMDL secundario (marcar como secundario)
            self.window_viewer_3d = PMDLViewerApp(self, pmdl_data, texture_path, is_secondary=True)
            
            # Bind para cerrar con ESC
            self.window_viewer_3d.bind("<Escape>", lambda e: self._return_from_3d_viewer())
            
            # Bind para cuando se cierre con X
            self.window_viewer_3d.protocol("WM_DELETE_WINDOW", self._return_from_3d_viewer)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el visor 3D:\n{e}")
            self.deiconify()

    
    # ------------ Carga / Render ------------

    @error_window_ui
    def on_open_file(self):
        """Abre y carga un archivo PMDL principal."""
        path = filedialog.askopenfilename(
            title="Selecciona un archivo .pmdl",
            filetypes=[("Pmdl files", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        self._load_and_render(path)
    
    def _load_and_render(self, path: str):
        """Carga un archivo PMDL y actualiza la UI."""
        try:
            with open(path, "rb") as f:
                blob = bytearray(f.read())
            hdr = parse_header(blob)
            parts = parse_parts_index(blob, hdr)
        except Exception as e:
            raise ValueError(f"No se pudo leer el .pmdl:\n{e}")

        
        self._blob = blob
        self._hdr = hdr
        self._parts = parts
        self._path = path
        
        # Mostrar ruta
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, os.path.basename(path))
        self.path_entry.configure(state="disabled")
        self.tooltip_path_entry.change_text(path)
        
        # Actualizar tabla
        self.parts_table.show_top_controls(self._hdr.part_count, self.on_import_part)
        self.parts_table.populate(self._parts)
        self.status_var.set(f"Archivo cargado: {os.path.basename(path)}")
    
    # ------------ Ediciones en memoria ------------
    
    def on_part_depth_changed(self, part_index: int, new_low_byte: int):
        """Callback: cambio de profundidad (capa)."""
        if self._parts and 0 <= part_index < len(self._parts):
            current = self._parts[part_index].part_id
            self._parts[part_index].part_id = (current & 0xFF00) | (new_low_byte & 0x00FF)
            self.status_var.set(f"Parte {part_index:02d}: Profundidad = {new_low_byte:02X}")
    
    def on_part_opacity_changed(self, part_index: int, new_percent: int):
        """Callback: cambio de opacidad."""
        if self._parts and 0 <= part_index < len(self._parts):
            from app.core import opacity_u16_from_percent
            self._parts[part_index].opacity = opacity_u16_from_percent(new_percent)
            self.status_var.set(f"Parte {part_index:02d}: Opacidad = {new_percent}%")
    
    def on_part_flag_changed(self, part_index: int, new_label: str):
        """Callback: cambio de función."""
        if self._parts and 0 <= part_index < len(self._parts):
            value = FLAG_MAP_LABEL_TO_VALUE.get(new_label, 0x00)
            self._parts[part_index].special_flag = value
            self.status_var.set(f"Parte {part_index:02d}: Función = '{new_label}' (0x{value:02X})")
    
    # ------------ Exportar parte ------------
    
    def on_export_part(self, part_index: int):
        """Exporta una parte como archivo .tttpart con encabezado de metadatos."""
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        
        if not (0 <= part_index < len(self._parts)):
            raise ValueError("Índice de parte inválido.")

        
        try:
            p = self._parts[part_index]
            
            # Exportar bytes de la parte
            part_data = export_part(self._blob, p)
            
            # Leer grosor del PMDL
            grosor_x, grosor_y, grosor_z = leer_grosor(self._blob)
            
            # Obtener metadatos de la parte
            capa = p.part_id & 0xFF
            opacidad = p.opacity
            flag = p.special_flag
            
            # Crear parte con encabezado
            part_with_header = exportar_parte_con_encabezado(
                part_data=part_data,
                grosor_x=grosor_x,
                grosor_y=grosor_y,
                grosor_z=grosor_z,
                capa=capa,
                opacidad=opacidad,
                flag=flag
            )
            
            base = os.path.splitext(os.path.basename(self._path))[0]
            default_name = f"{base}_parte_{part_index:02d}.tttpart"
            
            out_path = filedialog.asksaveasfilename(
                title="Exportar parte como .tttpart",
                defaultextension=".tttpart",
                initialfile=default_name,
                filetypes=[("TTT Part", "*.tttpart"), ("Todos los archivos", "*.*")]
            )
            
            if not out_path:
                return
            
            with open(out_path, "wb") as f:
                f.write(part_with_header)
            
            messagebox.showinfo("Exportado", f"Parte {part_index:02d} exportada con metadatos en:\n{out_path}")
            self.status_var.set(f"Parte {part_index:02d} exportada.")
        
        except Exception as e:
            raise ValueError(f"No se pudo exportar la parte:\n{e}")
    
    def on_delete_part(self, part_index: int):
        """Elimina una parte del PMDL."""
        if self._blob is None or self._hdr is None or not self._parts:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl o parche.")
            return
        
        try:
            delete_part(self._blob, self._hdr, self._parts, part_index)
            
            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            
            self.status_var.set("Parte borrada correctamente · Los ijue30s")
            messagebox.showinfo("Borrado", "Parte eliminada correctamente.")
        
        except Exception as e:
            raise ValueError(f"No se pudo borrar la parte:\n{e}")
    
    # ------------ Guardar ------------

    @error_window_ui
    def on_save(self):
        """Guarda los cambios en el archivo original o parche."""
        if self._blob is None or self._hdr is None or not self._parts:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl o parche.")
            return
        
        # Sincronizar datos de UI a memoria
        ui_data = self.parts_table.get_ui_data()
        sync_parts_from_ui(self._blob, self._hdr, self._parts, ui_data)
        
        # Si viene de un parche, manejar guardado a través del Character Editor
        if self.patch_bridge.is_from_patch():
            self._save_to_patch()
            return
        
        # Guardado normal de PMDL
        if not self._path:
            messagebox.showinfo("Info", "El archivo no tiene ruta de origen. Usa 'Guardar Como'.")
            return
        
        confirm = messagebox.askyesno(
            "Confirmar guardado",
            "¿Estás seguro de que deseas guardar el archivo?"
        )
        if not confirm:
            return
        
        try:
            # Guardar archivo
            with open(self._path, "wb") as f:
                f.write(self._blob)
            
            self.status_var.set("Cambios guardados.")
            messagebox.showinfo("Listo", "Cambios guardados en el .pmdl.")
        
        except Exception as e:
            raise ValueError(f"No se pudo guardar el archivo:\n{e}")

    @error_window_ui
    def on_save_as(self):
        """Guarda el PMDL con un nuevo nombre."""
        if self._blob is None or self._hdr is None or not self._parts:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl o parche.")
            return
        
        # Sincronizar datos de UI a memoria
        ui_data = self.parts_table.get_ui_data()
        sync_parts_from_ui(self._blob, self._hdr, self._parts, ui_data)
        
        # Si viene de un parche, manejar guardado a través del Character Editor
        if self.patch_bridge.is_from_patch():
            self._save_as_to_patch()
            return
        
        # Guardado normal de PMDL
        try:
            # Elegir destino
            initial = os.path.basename(self._path) if self._path else "nuevo.pmdl"
            out_path = filedialog.asksaveasfilename(
                title="Guardar como...",
                defaultextension=".pmdl",
                initialfile=initial,
                filetypes=[("PMDL", "*.pmdl"), ("Todos los archivos", "*.*")]
            )
            
            if not out_path:
                return
            
            # Guardar
            with open(out_path, "wb") as f:
                f.write(self._blob)
            
            # Actualizar estado
            self._path = out_path
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, os.path.basename(out_path))
            self.path_entry.configure(state="disabled")
            
            self.status_var.set(f"Guardado como: {os.path.basename(out_path)}")
            messagebox.showinfo("Listo", f"Guardado como:\n{out_path}")
        
        except Exception as e:
            raise ValueError(f"No se pudo guardar:\n{e}")
    
    # ------------ Importar Parte (.tttpart) ------------
    @error_window_ui
    def on_import_part(self):
        """Importa una parte desde archivo .tttpart (con o sin encabezado)."""
        if self._blob is None or self._hdr is None or self._parts is None:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        
        in_path = filedialog.askopenfilename(
            title="Selecciona una parte .tttpart",
            filetypes=[("TTT Part", "*.tttpart"), ("Todos los archivos", "*.*")]
        )
        if not in_path:
            return
        
        try:
            with open(in_path, "rb") as f:
                file_data = f.read()
            
            # Verificar estado del toggle de normalización
            normalize_enabled = self.normalize_toggle_var.get() if self.normalize_toggle_var else True
            
            # Procesar encabezado si existe
            part_data, metadata = importar_parte_con_encabezado(file_data)
            
            if metadata and normalize_enabled:
                # Tiene encabezado Y normalización activada
                # 1. Normalizar PMDL principal a grosor máximo si es necesario
                was_normalized = normalizar_pmdl_completo(self._blob, self._hdr.parts_index_offset, self._parts)
                if was_normalized:
                    print("✓ PMDL principal normalizado a grosor máximo")
                
                # 2. Convertir parte a grosor máximo
                part_converted = preparar_parte_externa_para_insercion(part_data, metadata['grosor'])
                
                # 3. Importar parte convertida
                new_offset, new_length = import_part(self._blob, self._hdr, self._parts, bytes(part_converted))
                
                # 4. Aplicar metadatos (opacidad, flag) a la parte recién insertada
                last_part = self._parts[-1]
                last_part.opacity = metadata['opacidad']
                last_part.special_flag = metadata['flag']
                
                # Actualizar en el blob
                base = self._hdr.parts_index_offset
                stride = 0x20
                last_idx = len(self._parts) - 1
                off = base + last_idx * stride
                
                import struct
                struct.pack_into("<H", self._blob, off + 0x02, last_part.opacity & 0xFFFF)
                struct.pack_into("<I", self._blob, off + 0x0C, last_part.special_flag & 0xFFFFFFFF)
                
                msg = f"Parte importada con normalización de grosor.\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}"
            
            elif metadata and not normalize_enabled:
                # Tiene encabezado PERO normalización desactivada
                new_offset, new_length = import_part(self._blob, self._hdr, self._parts, part_data)
                
                # Aplicar solo metadatos (opacidad, flag) sin conversión de grosor
                last_part = self._parts[-1]
                last_part.opacity = metadata['opacidad']
                last_part.special_flag = metadata['flag']
                
                base = self._hdr.parts_index_offset
                stride = 0x20
                last_idx = len(self._parts) - 1
                off = base + last_idx * stride
                
                import struct
                struct.pack_into("<H", self._blob, off + 0x02, last_part.opacity & 0xFFFF)
                struct.pack_into("<I", self._blob, off + 0x0C, last_part.special_flag & 0xFFFFFFFF)
                
                msg = f"Parte importada SIN normalización (toggle desactivado).\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}\n\n⚠️ ADVERTENCIA: Podría estar fuera de escala."
            
            else:
                # Sin encabezado - importación legacy
                new_offset, new_length = import_part(self._blob, self._hdr, self._parts, part_data)
                msg = f"Parte importada (sin encabezado).\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}\n\n⚠️ ADVERTENCIA: Podría estar fuera de escala."
            
            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            
            messagebox.showinfo("Importada", msg)
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar la parte:\n{e}")
            import traceback
            traceback.print_exc()
    
    def _save_to_patch(self):
        """Guarda el PMDL actualizado en el parche original."""
        # Actualizar PMDL en el parche
        if not self.patch_bridge.update_pmdl_in_patch(self._blob):
            messagebox.showerror("Error", "No se pudo actualizar el PMDL en el parche")
            return
        
        # Ocultar ventana principal
        self.withdraw()
        
        # Abrir Character Editor con el parche actualizado
        analyzer = self.patch_bridge.get_patch_analyzer()
        
        self.window_character_editor = CharacterEditorUI(
            self,
            is_secondary=False,
            on_open_in_editor_callback=None
        )
        
        # Bind para regresar
        self.window_character_editor.bind("<Escape>", lambda e: self._return_after_patch_save())
        self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_after_patch_save)
        
        # Cargar el parche actualizado en la UI
        self.window_character_editor.analyzer = analyzer
        self.window_character_editor.display_texture()
        self.window_character_editor.enable_buttons()
        
        # Llamar automáticamente a guardar
        self.window_character_editor.save_character()
    
    def _save_as_to_patch(self):
        """Guarda el PMDL actualizado en un nuevo archivo de parche."""
        # Actualizar PMDL en el parche
        if not self.patch_bridge.update_pmdl_in_patch(self._blob):
            messagebox.showerror("Error", "No se pudo actualizar el PMDL en el parche")
            return
        
        # Ocultar ventana principal
        self.withdraw()
        
        # Abrir Character Editor con el parche actualizado
        analyzer = self.patch_bridge.get_patch_analyzer()
        
        self.window_character_editor = CharacterEditorUI(
            self,
            is_secondary=False,
            on_open_in_editor_callback=None
        )
        
        # Bind para regresar
        self.window_character_editor.bind("<Escape>", lambda e: self._return_after_patch_save())
        self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_after_patch_save)
        
        # Cargar el parche actualizado en la UI
        self.window_character_editor.analyzer = analyzer
        self.window_character_editor.display_texture()
        self.window_character_editor.enable_buttons()
        
        # Llamar automáticamente a guardar como
        self.window_character_editor.save_character_as()
    
    def _return_after_patch_save(self):
        """Regresa a la ventana principal después de guardar el parche."""
        self._return_from_character_editor()
        self.patch_bridge.mark_saved()
    
    # ------------ PMDL Secundario ------------
    @error_window_ui
    def on_open_file_secondary(self):
        """Abre y carga un archivo PMDL secundario."""
        path = filedialog.askopenfilename(
            title="Selecciona un archivo .pmdl (secundario)",
            filetypes=[("Pmdl files", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        self._load_and_render_secondary(path)
    
    def _load_and_render_secondary(self, path: str):
        """Carga un PMDL secundario y actualiza la UI."""
        try:
            with open(path, "rb") as f:
                blob = bytearray(f.read())
            hdr = parse_header(blob)
            parts = parse_parts_index(blob, hdr)
        except Exception as e:
            raise ValueError(f"No se pudo leer el .pmdl secundario:\n{e}")

        
        self._blob2 = blob
        self._hdr2 = hdr
        self._parts2 = parts
        self._path2 = path
        
        # Mostrar ruta
        self.path2_entry.configure(state="normal")
        self.path2_entry.delete(0, tk.END)
        self.path2_entry.insert(0, os.path.basename(path))
        self.path2_entry.configure(state="disabled")
        self.tooltip_path2_entry.change_text(path)
        
        # Poblar tabla
        self.parts2_table.show_top_controls(self._hdr2.part_count)
        self.parts2_table.populate(self._parts2)
        
        self.status_var.set("PMDL secundario cargado · Los ijue30s")
    
    def on_add_part_from_secondary(self, part_index: int):
        """Agrega una parte del PMDL secundario al principal."""
        if self._blob is None or self._hdr is None or not self._parts:
            messagebox.showinfo("Info", "Abre primero un PMDL principal o parche.")
            return
        
        if self._blob2 is None or self._hdr2 is None or not self._parts2 or self._path2 is None:
            messagebox.showinfo("Info", "Importa primero un PMDL secundario.")
            return
        
        if not (0 <= part_index < len(self._parts2)):
            raise ValueError("Índice de parte (secundario) inválido.")

        
        try:
            # Verificar estado del toggle de normalización
            normalize_enabled = self.normalize_toggle_var.get() if self.normalize_toggle_var else True
            
            src = self._parts2[part_index]
            new_offset, new_length = add_part_from_secondary(
                self._blob, self._hdr, self._parts,
                self._blob2, src,
                normalize_thickness=normalize_enabled  # Pasar estado del toggle
            )
            
            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            
            if normalize_enabled:
                msg = f"Parte agregada con normalización de grosor.\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}"
            else:
                msg = f"Parte agregada SIN normalización (toggle desactivado).\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}\n\n⚠️ ADVERTENCIA: Podría estar fuera de escala."
            
            self.status_var.set("Parte agregada desde secundario · Los ijue30s")
            messagebox.showinfo("Listo", msg)
        
        except Exception as e:
            raise ValueError(f"No se pudo agregar la parte desde el secundario:\n{e}")
    
    def on_close_pmdl_main(self):
        """Cierra el PMDL principal y limpia la interfaz."""
        # Limpiar estado
        self._blob = None
        self._hdr = None
        self._parts = []
        self._path = None
        
        # Limpiar entry de ruta
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, tk.END)
        self.path_entry.configure(state="disabled")
        self.tooltip_path_entry.change_text("")
        
        # Limpiar tabla
        self.parts_table.clear()
        self.parts_table.hide_top_controls()
        
        self.status_var.set("PMDL principal cerrado · Los ijue30s")
    
    def on_close_pmdl_secondary(self):
        """Cierra el PMDL secundario y limpia la interfaz."""
        # Limpiar estado
        self._blob2 = None
        self._hdr2 = None
        self._parts2 = []
        self._path2 = None
        
        # Limpiar contexto del parche secundario si existe
        self.patch_bridge_secondary.clear_patch_context()
        
        # Limpiar entry de ruta
        self.path2_entry.configure(state="normal")
        self.path2_entry.delete(0, tk.END)
        self.path2_entry.configure(state="disabled")
        self.tooltip_path2_entry.change_text("")
        
        # Limpiar tabla y ocultar controles
        self.parts2_table.clear()
        self.parts2_table.hide_top_controls()
        
        self.status_var.set("PMDL secundario cerrado · Los ijue30s")


def run():
    """Función para iniciar la aplicación."""
    app = PmdlPartsApp()
    app.mainloop()