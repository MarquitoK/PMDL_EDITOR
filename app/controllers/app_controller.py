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
from app.ui.normalizador_window import NormalizadorWindow
from app.utils import center_window
from app.utils.thickness_normalizer import leer_grosor, normalizar_pmdl_completo, preparar_parte_externa_para_insercion
from app.utils.part_header import exportar_parte_con_encabezado, importar_parte_con_encabezado
from app.logic_sub_parts_pmdl.ui_pmdl_sub_parts import UiSubparts
from app.logic_patch import PatchBridge, CharacterEditorUI
from app.logic_3d.main_window import PMDLViewerApp
from app.logic_bones import BoneEditor
from app.utils.ui_error_window import error_window_ui
from app.utils.icon import set_app_icon

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
        set_app_icon(self)
        
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
            'on_close_pmdl_main': self.on_close_pmdl_main,
            'on_close_pmdl_secondary': self.on_close_pmdl_secondary,
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
        
        # Referencia para el editor de huesos
        self.window_bone_editor = None
        
        # Puente para manejo de parches
        self.patch_bridge = PatchBridge()
        
        # Puente para manejo de parches secundarios
        self.patch_bridge_secondary = PatchBridge()
        
        # Estado modo PMDF (cara extra abierta en el editor)
        self._pmdf_mode = False
        self._pmdf_face_name: Optional[str] = None
        self._pmdf_parent_analyzer = None  # CharacterAnalyzer original del parche
        
        # Configurar shortcuts de teclado
        self._bind_keyboard_shortcuts()
    
    def _build_menubar(self):
        self.menubar = MenuBar(self, height=28)
        self.menubar.pack(side="top", fill="x", pady=(0, 0))
        
        # Menú Archivo
        menu_archivo = self.menubar.add_menu("Archivo")
        # Guardar referencia al último widget añadido (botón del menú Archivo)
        children = self.menubar.winfo_children()
        self._menu_archivo_btn = children[-1] if children else None
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
        menu_tools.add_separator()
        menu_tools.add_command("Editor de Huesos", self.on_open_bone_editor, "Ctrl+H")
        menu_tools.add_separator()
        menu_tools.add_command("Normalizador de Escala", self.on_open_normalizador, "Ctrl+N")
        
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
        def _handle(key):
            """Devuelve handler que bloquea en modo PMDF si pmdf_block=True."""
            blocked_in_pmdf = key in ('o', 'p', 'r')
            def handler(e):
                if blocked_in_pmdf and self._pmdf_mode:
                    return "break"
                actions = {
                    'o':  self.on_open_file,
                    'p':  self.on_open_patch,
                    's':  self.on_save,
                    'S':  self.on_save_as,
                    't':  self.on_open_subparts_editor,
                    'd':  self.on_open_3d_viewer,
                    'h':  self.on_open_bone_editor,
                    'r':  self.on_open_character_editor,
                    'n':  self.on_open_normalizador,
                    'i':  lambda: self.on_import_part() if self._blob else None,
                    'O':  self.on_open_file_secondary,
                    'P':  self.on_open_patch_secondary,
                    'D':  self.on_visualize_secondary,
                }
                fn = actions.get(key)
                if fn:
                    fn()
                return "break"
            return handler

        # Archivo principal
        for k in ('o', 'O'):
            self.bind_all(f"<Control-{k}>", _handle('o'))
        for k in ('p', 'P'):
            self.bind_all(f"<Control-{k}>", _handle('p'))
        for k in ('s', 'S'):
            self.bind_all(f"<Control-{k}>", _handle('s'))
        self.bind_all("<Control-Shift-S>", _handle('S'))
        self.bind_all("<Control-Shift-s>", _handle('S'))

        # Tools
        for k in ('t', 'T'):
            self.bind_all(f"<Control-{k}>", _handle('t'))
        for k in ('d', 'D'):
            self.bind_all(f"<Control-{k}>", _handle('d'))
        for k in ('h', 'H'):
            self.bind_all(f"<Control-{k}>", _handle('h'))
        for k in ('r', 'R'):
            self.bind_all(f"<Control-{k}>", _handle('r'))
        for k in ('n', 'N'):
            self.bind_all(f"<Control-{k}>", _handle('n'))
        for k in ('i', 'I'):
            self.bind_all(f"<Control-{k}>", _handle('i'))

        # Archivo Secundario
        self.bind_all("<Control-Shift-O>", _handle('O'))
        self.bind_all("<Control-Shift-o>", _handle('O'))
        self.bind_all("<Control-Shift-P>", _handle('P'))
        self.bind_all("<Control-Shift-p>", _handle('P'))
        self.bind_all("<Control-Shift-D>", _handle('D'))
        self.bind_all("<Control-Shift-d>", _handle('D'))
    
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
            if not self._blob and not self._blob2:
                messagebox.showinfo("Info", "Abre primero un PMDL principal o secundario.")
                return
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
                center_window(self.window_viewer_3d, 1280, 720)
                
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
    
    def on_open_normalizador(self):
        self.withdraw()
        win = NormalizadorWindow(self)
        win.bind("<Escape>", lambda e: self._return_from_normalizador(win))
        win.protocol("WM_DELETE_WINDOW", lambda: self._return_from_normalizador(win))

    def _return_from_normalizador(self, win):
        if win.winfo_exists():
            win.destroy()
        self.deiconify()

    def on_open_bone_editor(self):
        """Abre el Editor de Huesos con intercambio de ventanas."""
        if self.window_bone_editor is None or not self.window_bone_editor.winfo_exists():
            if not self._blob:
                messagebox.showinfo("Info", "Abre primero un PMDL principal.")
                return
            # Recoger bytes del PMDL activo
            pmdl_bytes  = None
            bones_data  = None
            bones_names = {}

            if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
                viewer = self.window_viewer_3d
                try:
                    if viewer.temp_pmdl_path and os.path.exists(viewer.temp_pmdl_path):
                        with open(viewer.temp_pmdl_path, 'rb') as f:
                            pmdl_bytes = bytearray(f.read())
                except Exception:
                    pass
                try:
                    if hasattr(viewer, 'gl_viewport') and viewer.gl_viewport:
                        bones_data  = viewer.gl_viewport.bones_data
                        bones_names = viewer.gl_viewport.bones_names or {}
                except Exception:
                    pass
            elif self._blob:
                pmdl_bytes = bytearray(self._blob)

            self.withdraw()

            self.window_bone_editor = BoneEditor(self, pmdl_bytes=pmdl_bytes,
                                                  bones_names=bones_names)
            center_window(self.window_bone_editor, 1100, 680)

            # Pasar huesos ya cargados si vienen del visor
            if bones_data:
                self.window_bone_editor.after(
                    150,
                    lambda: self.window_bone_editor.receive_bones(
                        bones_data, pmdl_bytes, bones_names
                    )
                )

            self.window_bone_editor.on_close_requested = self._return_from_bone_editor
        else:
            self.window_bone_editor.focus()
            self.window_bone_editor.lift()

    def _return_from_bone_editor(self):
        if self.window_bone_editor and self.window_bone_editor.winfo_exists():
            # Recuperar PMDL con los cambios de huesos
            modified = self.window_bone_editor.get_modified_pmdl()
            if modified:
                self._blob = modified
                # Re-parsear header y partes
                try:
                    self._hdr = parse_header(self._blob)
                    self._parts = parse_parts_index(self._blob, self._hdr)
                    if hasattr(self, 'parts_table'):
                        self.parts_table.populate(self._parts)
                        self.parts_table.update_part_count(self._hdr.part_count)
                except Exception as e:
                    print(f"Error re-parseando PMDL tras editor de huesos: {e}")

                # Si viene de parche, actualizar el parche también
                if self.patch_bridge.is_from_patch():
                    try:
                        self.patch_bridge.update_pmdl_in_patch(self._blob)
                        # Refrescar texture_info porque el tamaño del PMDL cambió
                        analyzer = self.patch_bridge.get_patch_analyzer()
                        if analyzer:
                            analyzer.find_pmdl_and_texture()
                    except Exception as e:
                        print(f"Error actualizando parche con huesos: {e}")

                # Si hay visor 3D abierto, recargar huesos y re-extraer textura
                if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
                    try:
                        viewer = self.window_viewer_3d
                        if viewer.temp_pmdl_path:
                            with open(viewer.temp_pmdl_path, 'wb') as f:
                                f.write(self._blob)
                            viewer._load_bones(self._blob)
                        # Re-extraer textura desde el parche porque el tamaño del PMDL cambió
                        if self.patch_bridge.is_from_patch():
                            analyzer = self.patch_bridge.get_patch_analyzer()
                            if analyzer and analyzer.texture_info:
                                try:
                                    import tempfile
                                    img = analyzer.generate_texture_image()
                                    if img:
                                        if viewer.temp_texture_path and os.path.exists(viewer.temp_texture_path):
                                            try:
                                                os.unlink(viewer.temp_texture_path)
                                            except Exception:
                                                pass
                                        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp:
                                            img.save(tmp.name)
                                            viewer.temp_texture_path = tmp.name
                                        if hasattr(viewer, 'gl_viewport') and viewer.gl_viewport:
                                            viewer.gl_viewport.load_texture(viewer.temp_texture_path)
                                except Exception as e:
                                    print(f"Error re-extrayendo textura tras bone editor: {e}")
                    except Exception as e:
                        print(f"Error recargando huesos en visor 3D: {e}")

            self.window_bone_editor.destroy()
        self.window_bone_editor = None
        self.deiconify()
        self.focus_force()

    def _return_from_3d_viewer(self, skip_unsaved_check=False):
        # Cierra el visor 3D y regresa a la ventana principal
        if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
            if (not skip_unsaved_check and
                    hasattr(self.window_viewer_3d, 'has_unsaved_changes') and
                    self.window_viewer_3d.has_unsaved_changes):
                respuesta = messagebox.askyesnocancel(
                    "Cambios sin guardar",
                    "Hay cambios sin guardar en el editor de UVs.\n¿Deseas aplicar los cambios antes de cerrar?",
                    icon="warning"
                )
                if respuesta is None:
                    # Cancelar — no cerrar
                    return
                if respuesta:
                    # Sí — aplicar cambios
                    modified_pmdl = self.window_viewer_3d.get_modified_pmdl_data()
                    if modified_pmdl:
                        self._blob = bytearray(modified_pmdl)
                        if self.patch_bridge.is_from_patch():
                            try:
                                analyzer = self.patch_bridge.get_patch_analyzer()
                                if analyzer and hasattr(analyzer, 'character_data'):
                                    analyzer.character_data['pmdl_blob'] = bytes(self._blob)
                                    analyzer.save_patch()
                                    print("✓ Cambios de UVs guardados en el parche automáticamente")
                            except Exception as e:
                                print(f"Error al guardar cambios de UVs en parche: {e}")
                        try:
                            self._hdr = parse_header(self._blob)
                            self._parts = parse_parts_index(self._blob, self._hdr)
                            if hasattr(self, 'parts_table'):
                                self.parts_table.populate(self._parts)
                                self.parts_table.update_part_count(self._hdr.part_count)
                        except Exception as e:
                            print(f"Error al re-analizar PMDL: {e}")
                # No — descartar cambios, cerrar sin aplicar

            self.window_viewer_3d.cleanup()
            self.window_viewer_3d.destroy()
        self.window_viewer_3d = None

        # Mostrar ventana principal
        self.deiconify()
        self.focus_force()
    
    def on_open_character_editor(self):
        if self._pmdf_mode:
            return

        # Abre el Character Editor como sub-herramienta
        if self.window_character_editor is None or not self.window_character_editor.winfo_exists():
            self.withdraw()
            
            has_patch = self.patch_bridge.is_from_patch()
            
            self.window_character_editor = CharacterEditorUI(
                self,
                is_secondary=False,
                on_open_in_editor_callback=self._on_load_pmdl_from_patch,
                from_patch=False
            )
            
            if has_patch:
                analyzer = self.patch_bridge.get_patch_analyzer()
                if analyzer:
                    # Usar el analyzer en memoria (no recargar desde disco)
                    self.window_character_editor.analyzer = analyzer
                    self.window_character_editor.display_texture()
                    self.window_character_editor.enable_buttons()
            
            self.window_character_editor.bind("<Escape>", lambda e: self._return_from_character_editor())
            self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_from_character_editor)
        else:
            self.window_character_editor.focus()
            self.window_character_editor.lift()
        self.focus()
        self.lift()
    
    def _on_load_pmdl_from_patch(self, analyzer):
        from app.logic_patch.character_ui import FaceAnalyzerWrapper

        if isinstance(analyzer, FaceAnalyzerWrapper):
            self._on_load_pmdf_from_face(analyzer)
            return

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

    def _on_load_pmdf_from_face(self, face_analyzer):
        """Carga un PMDF (cara extra) en el editor en modo PMDF."""
        from app.logic_patch.character_ui import FaceAnalyzerWrapper
        pmdl_data = face_analyzer.get_pmdl_data()
        if not pmdl_data:
            messagebox.showerror("Error", "No se pudo extraer el PMDF")
            return

        try:
            hdr = parse_header(pmdl_data)
            parts = parse_parts_index(pmdl_data, hdr)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo parsear el PMDF:\n{e}")
            return

        # Guardar contexto del parche principal (si viene de uno)
        patch_path = face_analyzer.file_path
        self.patch_bridge.set_patch_context(patch_path, face_analyzer, is_secondary=False)

        self._return_from_character_editor()

        self._blob = pmdl_data
        self._hdr = hdr
        self._parts = parts
        self._path = f"[PMDF]{patch_path}::{face_analyzer.face_name}"

        # Estado modo PMDF
        self._pmdf_mode = True
        self._pmdf_face_name = face_analyzer.face_name
        self._pmdf_parent_analyzer = face_analyzer.parent_analyzer

        # Actualizar entry de ruta
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, f"[PMDF] {face_analyzer.face_name}")
        self.path_entry.configure(state="disabled")
        self.tooltip_path_entry.change_text(
            f"PMDF '{face_analyzer.face_name}' extraído de: {patch_path}"
        )

        # Poblar tabla
        self.parts_table.show_top_controls(self._hdr.part_count, self.on_import_part)
        self.parts_table.populate(self._parts)

        self.status_var.set(f"PMDF '{face_analyzer.face_name}' cargado · Los ijue30s")

        # Activar modo PMDF en la UI
        self._enter_pmdf_mode()

    def _enter_pmdf_mode(self):
        if self._menu_archivo_btn and self._menu_archivo_btn.winfo_exists():
            self._menu_archivo_btn.pack_forget()
        self.parts_table.set_pmdf_mode(True, self.on_save_pmdf)

    def _exit_pmdf_mode(self):
        self._pmdf_mode = False
        self._pmdf_face_name = None
        self._pmdf_parent_analyzer = None
        if self._menu_archivo_btn and self._menu_archivo_btn.winfo_exists():
            # Insertar antes del primer hijo visible del menubar
            children = [w for w in self.menubar.winfo_children()
                        if w is not self._menu_archivo_btn and w.winfo_ismapped()]
            if children:
                self._menu_archivo_btn.pack(side="left", padx=1, pady=1, before=children[0])
            else:
                self._menu_archivo_btn.pack(side="left", padx=1, pady=1)
        self.parts_table.set_pmdf_mode(False, None)

    @error_window_ui
    def on_save_pmdf(self):
        """Guarda el PMDF editado de vuelta al parche en memoria y abre el Character Editor."""
        if not self._pmdf_mode or not self._pmdf_face_name or not self._pmdf_parent_analyzer:
            return

        # Sincronizar UI → memoria
        ui_data = self.parts_table.get_ui_data()
        sync_parts_from_ui(self._blob, self._hdr, self._parts, ui_data)

        # Empujar cambios al parent_analyzer (CharacterAnalyzer real)
        success = self._pmdf_parent_analyzer.set_face_data(self._pmdf_face_name, bytes(self._blob))
        if not success:
            messagebox.showerror("Error", "No se pudo guardar el PMDF en el parche")
            return

        face_name = self._pmdf_face_name
        parent_analyzer = self._pmdf_parent_analyzer
        patch_path = parent_analyzer.file_path

        self.status_var.set(f"PMDF '{face_name}' guardado en memoria · Los ijue30s")

        # Salir de modo PMDF y limpiar editor
        self._exit_pmdf_mode()
        self.patch_bridge.clear_patch_context()
        self.on_close_pmdl_main()

        # Abrir Character Editor con el parche actualizado en memoria
        self.withdraw()
        self.window_character_editor = CharacterEditorUI(
            self,
            is_secondary=False,
            on_open_in_editor_callback=self._on_load_pmdl_from_patch,
            from_patch=False
        )
        self.window_character_editor.analyzer = parent_analyzer
        self.window_character_editor.display_texture()
        self.window_character_editor.enable_buttons()

        self.window_character_editor.bind("<Escape>", lambda e: self._return_from_character_editor())
        self.window_character_editor.protocol("WM_DELETE_WINDOW", self._return_from_character_editor)
    
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
        if self._pmdf_mode:
            return
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
        
        # Abrir Character Editor con UI limitada (solo exportar textura)
        self.window_character_editor = CharacterEditorUI(
            self,
            is_secondary=False,
            on_open_in_editor_callback=self._on_load_pmdl_from_patch,
            from_patch=True
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
        if self._pmdf_mode:
            return
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
            
            self._refresh_patch_texture()
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

        if self._pmdf_mode:
            self.on_save_pmdf()
            return
        
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

        if self._pmdf_mode:
            self.on_save_pmdf()
            return
        
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
        """Importa una o más partes desde archivos .tttpart (con o sin encabezado)."""
        if self._blob is None or self._hdr is None or self._parts is None:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return

        in_paths = filedialog.askopenfilenames(
            title="Selecciona una o más partes .tttpart",
            filetypes=[("TTT Part", "*.tttpart"), ("Todos los archivos", "*.*")]
        )
        if not in_paths:
            return

        normalize_enabled = self.normalize_toggle_var.get() if self.normalize_toggle_var else True
        resultados = []
        errores = []

        for in_path in in_paths:
            nombre = os.path.basename(in_path)
            try:
                with open(in_path, "rb") as f:
                    file_data = f.read()

                part_data, metadata = importar_parte_con_encabezado(file_data)

                if metadata and normalize_enabled:
                    was_normalized = normalizar_pmdl_completo(self._blob, self._hdr.parts_index_offset, self._parts)
                    if was_normalized:
                        print("✓ PMDL principal normalizado a grosor máximo")
                    part_converted = preparar_parte_externa_para_insercion(part_data, metadata['grosor'])
                    new_offset, new_length = import_part(self._blob, self._hdr, self._parts, bytes(part_converted))
                    last_part = self._parts[-1]
                    last_part.opacity = metadata['opacidad']
                    last_part.special_flag = metadata['flag']
                    off = self._hdr.parts_index_offset + (len(self._parts) - 1) * 0x20
                    import struct
                    struct.pack_into("<H", self._blob, off + 0x02, last_part.opacity & 0xFFFF)
                    struct.pack_into("<I", self._blob, off + 0x0C, last_part.special_flag & 0xFFFFFFFF)
                    resultados.append(f"✓ {nombre} — con normalización (0x{new_offset:X}, 0x{new_length:X})")

                elif metadata and not normalize_enabled:
                    new_offset, new_length = import_part(self._blob, self._hdr, self._parts, part_data)
                    last_part = self._parts[-1]
                    last_part.opacity = metadata['opacidad']
                    last_part.special_flag = metadata['flag']
                    off = self._hdr.parts_index_offset + (len(self._parts) - 1) * 0x20
                    import struct
                    struct.pack_into("<H", self._blob, off + 0x02, last_part.opacity & 0xFFFF)
                    struct.pack_into("<I", self._blob, off + 0x0C, last_part.special_flag & 0xFFFFFFFF)
                    resultados.append(f"⚠ {nombre} — SIN normalización (0x{new_offset:X}, 0x{new_length:X})")

                else:
                    new_offset, new_length = import_part(self._blob, self._hdr, self._parts, part_data)
                    resultados.append(f"⚠ {nombre} — sin encabezado (0x{new_offset:X}, 0x{new_length:X})")

            except Exception as e:
                errores.append(f"✗ {nombre}: {e}")
                import traceback
                traceback.print_exc()

        self.parts_table.populate(self._parts)
        self.parts_table.update_part_count(self._hdr.part_count)

        self._refresh_patch_texture()

        resumen = "\n".join(resultados)
        if errores:
            resumen += "\n\nErrores:\n" + "\n".join(errores)
        messagebox.showinfo("Importación completada", resumen if resumen else "Sin resultados.")
    
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
    
    def _refresh_patch_texture(self):
        """Re-lee la tex del parche tras cambios de tamaño en el PMDL."""
        if not self.patch_bridge.is_from_patch():
            return
        analyzer = self.patch_bridge.get_patch_analyzer()
        if not analyzer:
            return
        try:
            self.patch_bridge.update_pmdl_in_patch(self._blob)
            analyzer.find_pmdl_and_texture()
        except Exception as e:
            print(f"Error refrescando tex del parche: {e}")
            return

        # Actualizar character editor si está abierto
        if self.window_character_editor and self.window_character_editor.winfo_exists():
            try:
                self.window_character_editor.analyzer = analyzer
                self.window_character_editor.display_texture()
            except Exception as e:
                print(f"Error actualizando tex en character editor: {e}")

        # Actualizar visor 3D si está abierto
        if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
            try:
                import tempfile
                img = analyzer.generate_texture_image()
                if img:
                    viewer = self.window_viewer_3d
                    if viewer.temp_texture_path and os.path.exists(viewer.temp_texture_path):
                        try:
                            os.unlink(viewer.temp_texture_path)
                        except Exception:
                            pass
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as tmp:
                        img.save(tmp.name)
                        viewer.temp_texture_path = tmp.name
                    if hasattr(viewer, 'gl_viewport') and viewer.gl_viewport:
                        viewer.gl_viewport.load_texture(viewer.temp_texture_path)
            except Exception as e:
                print(f"Error actualizando tex en visor 3D: {e}")

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
            
            self._refresh_patch_texture()
            
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
        if self._pmdf_mode:
            self._exit_pmdf_mode()
            self.patch_bridge.clear_patch_context()

        # Cerrar ventanas dependientes del PMDL principal
        if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
            self._return_from_3d_viewer(skip_unsaved_check=True)
        if self.window_subparts and self.window_subparts.winfo_exists():
            self._return_from_subparts()
        if self.window_bone_editor and self.window_bone_editor.winfo_exists():
            self.window_bone_editor.destroy()
            self.window_bone_editor = None

        self.patch_bridge.clear_patch_context()

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
        # Cerrar visor 3D si estaba mostrando el secundario
        if self.window_viewer_3d and self.window_viewer_3d.winfo_exists():
            try:
                if getattr(self.window_viewer_3d, 'is_secondary', False):
                    self._return_from_3d_viewer(skip_unsaved_check=True)
            except Exception:
                pass

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