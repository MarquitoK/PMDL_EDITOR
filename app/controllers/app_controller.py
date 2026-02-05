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
from app.utils import center_window
from app.logic_sub_parts_pmdl.ui_pmdl_sub_parts import UiSubparts


APP_TITLE = "Pmdl Editor (TTT) · By Los ijue30s · v1.4.1"
GEOMETRY = (880,550)


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
        
        # Construir UI
        callbacks = {
            'on_open_file': self.on_open_file,
            'on_save': self.on_save,
            'on_save_as': self.on_save_as,
            'on_part_depth_changed': self.on_part_depth_changed,
            'on_part_opacity_changed': self.on_part_opacity_changed,
            'on_part_flag_changed': self.on_part_flag_changed,
            'on_export_part': self.on_export_part,
            'on_delete_part': self.on_delete_part,
            'on_open_file_secondary': self.on_open_file_secondary,
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

        # llamado temporal a la ventana subpart
        self.window_subparts = UiSubparts(self)
    
    def on_close(self):
        """Confirmación antes de cerrar la aplicación."""
        if messagebox.askyesno("Salir", "¿Estas seguro de que deseas cerrar la aplicacion?"):
            self.destroy()
    
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


def run():
    """Función para iniciar la aplicación."""
    app = PmdlPartsApp()
    app.mainloop()