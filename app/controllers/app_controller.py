import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from typing import Optional, List

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
from app.logic_sub_parts_pmdl.ui_pmdl_sub_parts import UiSubparts


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

        # Referencia para la ventana de subparts
        self.window_subparts = None
        
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
        menu_tools.add_command("SubParts Editor", self.on_open_subparts_editor, "Ctrl+T")
        
        # Menú Opciones
        menu_opciones = self.menubar.add_menu("Opciones")
        # Aquí se agregarán opciones en el futuro
        
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
        
        # Archivo Secundario
        self.bind("<Control-Shift-O>", lambda e: self.on_open_file_secondary())
        self.bind("<Control-Shift-o>", lambda e: self.on_open_file_secondary())
        
        self.bind("<Control-Shift-P>", lambda e: self.on_open_patch_secondary())
        self.bind("<Control-Shift-p>", lambda e: self.on_open_patch_secondary())
        
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
    
    def on_open_subparts_editor(self):
        """Abre el editor de SubParts."""
        if not self._path and not self._path2:
            messagebox.showinfo("Informacion", "Abre al menos un archivo para editar")
            return

        if self.window_subparts is None or not self.window_subparts.winfo_exists():
            self.window_subparts = UiSubparts(self)
        else:
            # Si ya existe, traerla al frente
            self.window_subparts.focus()
            self.window_subparts.lift()
    
    def on_open_patch(self):
        """Placeholder para abrir parche principal."""
        messagebox.showinfo("Próximamente", "Función 'Abrir Parche' en desarrollo.")
    
    def on_open_patch_secondary(self):
        """Placeholder para abrir parche secundario."""
        messagebox.showinfo("Próximamente", "Función 'Abrir Parche Secundario' en desarrollo.")
    
    # ------------ Carga / Render ------------
    
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
            messagebox.showerror("Error", f"No se pudo leer el .pmdl:\n{e}")
            return
        
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
        """Exporta una parte como archivo .tttpart."""
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        
        if not (0 <= part_index < len(self._parts)):
            messagebox.showerror("Error", "Índice de parte inválido.")
            return
        
        try:
            p = self._parts[part_index]
            chunk = export_part(self._blob, p)
            
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
                f.write(chunk)
            
            messagebox.showinfo("Exportado", f"Parte {part_index:02d} exportada en:\n{out_path}")
            self.status_var.set(f"Parte {part_index:02d} exportada.")
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la parte:\n{e}")
    
    def on_delete_part(self, part_index: int):
        """Elimina una parte del PMDL."""
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        
        try:
            delete_part(self._blob, self._hdr, self._parts, part_index)
            
            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            
            self.status_var.set("Parte borrada correctamente · Los ijue30s")
            messagebox.showinfo("Borrado", "Parte eliminada correctamente.")
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo borrar la parte:\n{e}")
    
    # ------------ Guardar ------------
    
    def on_save(self):
        """Guarda los cambios en el archivo original."""
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        
        confirm = messagebox.askyesno(
            "Confirmar guardado",
            "¿Estas seguro de que deseas guardar el archivo?"
        )
        if not confirm:
            return
        
        try:
            # Sincronizar datos de UI a memoria
            ui_data = self.parts_table.get_ui_data()
            sync_parts_from_ui(self._blob, self._hdr, self._parts, ui_data)
            
            # Guardar archivo
            with open(self._path, "wb") as f:
                f.write(self._blob)
            
            self.status_var.set("Cambios guardados.")
            messagebox.showinfo("Listo", "Cambios guardados en el .pmdl.")
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{e}")
    
    def on_save_as(self):
        """Guarda el PMDL con un nuevo nombre."""
        if self._blob is None or self._hdr is None or not self._parts:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        
        try:
            # Sincronizar datos de UI a memoria
            ui_data = self.parts_table.get_ui_data()
            sync_parts_from_ui(self._blob, self._hdr, self._parts, ui_data)
            
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
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
    
    # ------------ Importar Parte (.tttpart) ------------
    
    def on_import_part(self):
        """Importa una parte desde archivo .tttpart."""
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
                new_part_data = f.read()
            
            new_offset, new_length = import_part(self._blob, self._hdr, self._parts, new_part_data)
            
            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            
            messagebox.showinfo(
                "Importada",
                f"Parte añadida correctamente.\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}"
            )
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar la parte:\n{e}")
    
    # ------------ PMDL Secundario ------------
    
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
            messagebox.showerror("Error", f"No se pudo leer el .pmdl secundario:\n{e}")
            return
        
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
        self.parts2_table.update_part_count(self._hdr2.part_count)
        self.parts2_table.populate(self._parts2)
        
        self.status_var.set("PMDL secundario cargado · Los ijue30s")
    
    def on_add_part_from_secondary(self, part_index: int):
        """Agrega una parte del PMDL secundario al principal."""
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un PMDL principal.")
            return
        
        if self._blob2 is None or self._hdr2 is None or not self._parts2 or self._path2 is None:
            messagebox.showinfo("Info", "Importa primero un PMDL secundario.")
            return
        
        if not (0 <= part_index < len(self._parts2)):
            messagebox.showerror("Error", "Índice de parte (secundario) inválido.")
            return
        
        try:
            src = self._parts2[part_index]
            new_offset, new_length = add_part_from_secondary(
                self._blob, self._hdr, self._parts,
                self._blob2, src
            )
            
            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            
            self.status_var.set("Parte agregada desde secundario · Los ijue30s")
            messagebox.showinfo(
                "Listo",
                f"Parte agregada desde secundario.\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}"
            )
        
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo agregar la parte desde el secundario:\n{e}")
    
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
        
        # Limpiar entry de ruta
        self.path2_entry.configure(state="normal")
        self.path2_entry.delete(0, tk.END)
        self.path2_entry.configure(state="disabled")
        self.tooltip_path2_entry.change_text("")
        
        # Limpiar tabla
        self.parts2_table.clear()
        self.parts2_table.update_part_count(0)
        self.parts2_table._parts_count_label.configure(text="Partes: -")
        
        self.status_var.set("PMDL secundario cerrado · Los ijue30s")


def run():
    """Función para iniciar la aplicación."""
    app = PmdlPartsApp()
    app.mainloop()