import os
import struct
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from dataclasses import dataclass
from typing import List, Optional
from app.ui.tooltip import ToolTip


APP_TITLE = "Pmdl Editor (TTT) · By Los ijue30s · v1.4.1"
UI_FONT = ("Segoe UI", 12)

@dataclass
class PmdlHeader:
    magic: bytes
    bone_count: int
    bones_offset: int
    part_count: int
    parts_index_offset: int

@dataclass
class PartIndexEntry:
    part_id: int
    opacity: int
    part_offset: int
    part_length: int
    special_flag: int

def percent_from_opacity_u16(u16: int) -> int:
    if u16 <= 0: return 0
    if u16 >= 0xFFFF: return 100
    return round(u16 * 100 / 0xFFFF)

def opacity_u16_from_percent(pct: int) -> int:
    pct = max(0, min(100, int(pct)))
    if pct == 100: return 0xFFFF
    if pct == 0:   return 0x0000
    return int(round(pct * 0xFFFF / 100.0))

FLAG_MAP_VALUE_TO_LABEL = {
    0x00: "Ninguna",
    0x01: "Equip. 1",
    0x02: "Equip. 2",
    0x06: "Cara",
    0x07: "Ocultable",
}
FLAG_MAP_LABEL_TO_VALUE = {v: k for k, v in FLAG_MAP_VALUE_TO_LABEL.items()}
FLAG_OPTIONS_LABELS = list(FLAG_MAP_LABEL_TO_VALUE.keys())

def parse_header(blob: bytes) -> PmdlHeader:
    if len(blob) < 0x70:
        raise ValueError("Archivo demasiado corto para cabecera .pmdl (0x70 bytes).")
    magic = blob[0x00:0x04]
    if magic != b"pMdl":
        raise ValueError(f"Firma inválida: {magic} (se esperaba b'pMdl').")
    bone_count = blob[0x08]
    bones_offset = struct.unpack_from("<I", blob, 0x50)[0]
    part_count = struct.unpack_from("<I", blob, 0x5C)[0]
    parts_index_offset = struct.unpack_from("<I", blob, 0x60)[0]
    return PmdlHeader(magic, bone_count, bones_offset, part_count, parts_index_offset)

def parse_parts_index(blob: bytes, hdr: PmdlHeader) -> List[PartIndexEntry]:
    entries: List[PartIndexEntry] = []
    base = hdr.parts_index_offset
    size = 0x20
    for i in range(hdr.part_count):
        off = base + i * size
        chunk = blob[off:off+size]
        if len(chunk) < size:
            raise ValueError(f"Índice de partes incompleto en entrada {i}.")
        part_id,      = struct.unpack_from("<H", chunk, 0x00)
        opacity,      = struct.unpack_from("<H", chunk, 0x02)
        part_offset,  = struct.unpack_from("<I", chunk, 0x04)
        part_length,  = struct.unpack_from("<I", chunk, 0x08)
        special_flag, = struct.unpack_from("<I", chunk, 0x0C)
        entries.append(PartIndexEntry(part_id, opacity, part_offset, part_length, special_flag))
    return entries

class PartsTable(ctk.CTkScrollableFrame):
    def __init__(self, master, on_depth_change, on_opacity_change, on_flag_change, on_export_part, on_delete_part):
        super().__init__(master, corner_radius=8)

        self.on_depth_change = on_depth_change
        self.on_opacity_change = on_opacity_change
        self.on_flag_change = on_flag_change
        self.on_export_part = on_export_part
        self.on_delete_part = on_delete_part

        # Estado UI
        self._rows_widgets = []
        self._controls_frame = None
        self._parts_count_label = None
        self._top_import_btn = None

        # Encabezados (fila 1)
        headers = ["Capa", "Nombre", "Tamaño", "Opacidad", "Función", "Exportar Parte"]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self, text=text, font=("Segoe UI", 12))
            lbl.grid(row=1, column=col, padx=(6, 4), pady=(4, 4), sticky="w")

        # Columnas
        self.grid_columnconfigure(0, weight=0)  # Capa
        self.grid_columnconfigure(1, weight=1)  # Nombre
        self.grid_columnconfigure(2, weight=0)  # Tamaño
        self.grid_columnconfigure(3, weight=0)  # Opacidad
        self.grid_columnconfigure(4, weight=0)  # Función
        self.grid_columnconfigure(5, weight=0)  # Exportar Parte

        # Validación para el campo hex (Capa)
        self._vcmd = (self.register(self._validate_hex_keystroke), "%P")

    # ----- Cabecera superior dinámica (fila 0) -----

    def show_top_controls(self, part_count: int, on_import_part_cb):
        # Destruye si existe (refresco)
        if self._controls_frame is not None:
            try: self._controls_frame.destroy()
            except Exception: pass
            self._controls_frame = None
            self._parts_count_label = None
            self._top_import_btn = None

        self._controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._controls_frame.grid(row=0, column=0, columnspan=6, padx=(6, 4), pady=(4, 0), sticky="we")

        self._top_import_btn = ctk.CTkButton(
            self._controls_frame, text="Importar Parte", width=120, height=24,
            font=("Segoe UI", 12), command=on_import_part_cb
        )
        self._top_import_btn.pack(side="left", padx=(0, 8))

        self._parts_count_label = ctk.CTkLabel(
            self._controls_frame, text=f"Partes: {part_count}", font=("Segoe UI", 12)
        )
        self._parts_count_label.pack(side="left", padx=(0, 8))

    def hide_top_controls(self):
        if self._controls_frame is not None:
            try: self._controls_frame.destroy()
            except Exception: pass
            self._controls_frame = None
            self._parts_count_label = None
            self._top_import_btn = None

    def update_part_count(self, part_count: int):
        if self._parts_count_label is not None:
            self._parts_count_label.configure(text=f"Partes: {part_count}")

    # ----- Tabla de datos -----

    def clear(self):
        for ws in self._rows_widgets:
            for w in ws:
                try: w.destroy()
                except Exception: pass
        self._rows_widgets.clear()

    def populate(self, parts: List[PartIndexEntry]):
        self.clear()

        for i, p in enumerate(parts):
            row = i + 2

            # Capa
            depth_hex = f"{p.part_id & 0xFF:02X}"
            depth_entry = ctk.CTkEntry(self, width=56, justify="center", font=("Segoe UI", 12))
            depth_entry.insert(0, depth_hex)
            depth_entry.configure(validate="key", validatecommand=self._vcmd)
            depth_entry.bind("<FocusOut>", lambda e, idx=i: self._commit_depth(e.widget.get(), idx, e.widget))
            depth_entry.bind("<Return>",   lambda e, idx=i: self._commit_depth(e.widget.get(), idx, e.widget))
            depth_entry.grid(row=row, column=0, padx=(6, 4), pady=(2, 2), sticky="w")

            # Nombre
            name_lbl = ctk.CTkLabel(self, text=f"Parte_{i}", font=("Segoe UI", 12))
            name_lbl.grid(row=row, column=1, padx=(6, 4), pady=(2, 2), sticky="w")

            # Tamaño
            size_lbl = ctk.CTkLabel(self, text=f"{p.part_length:X}", font=("Segoe UI", 12))
            size_lbl.grid(row=row, column=2, padx=(6, 4), pady=(2, 2), sticky="w")

            # Opacidad
            if p.opacity <= 0:
                pct = 0
            elif p.opacity >= 0xFFFF:
                pct = 100
            else:
                pct = round(p.opacity * 100 / 0xFFFF)

            pct_lbl = ctk.CTkLabel(self, text=f"{pct}%", width=36, font=("Segoe UI", 12))
            pct_lbl.grid(row=row, column=3, padx=(6, 2), pady=(2, 2), sticky="w")

            slider = ctk.CTkSlider(self, from_=0, to=100, number_of_steps=100, width=60, height=10)
            slider.set(pct)
            slider.configure(command=lambda val, idx=i, lbl=pct_lbl: self._on_opacity(val, idx, lbl))
            slider.grid(row=row, column=3, padx=(46, 2), pady=(2, 2), sticky="w")

            # Función
            init_label = FLAG_MAP_VALUE_TO_LABEL.get(p.special_flag, "Ninguna")
            flag_var = tk.StringVar(value=init_label)

            flag_opt = ctk.CTkComboBox(
                self,
                values=list(FLAG_MAP_VALUE_TO_LABEL.values()),
                variable=flag_var,
                width=100,                 # ancho fijo real
                font=("Segoe UI", 12),
                state="readonly",          # solo selección (desplegable)
                command=lambda new_label, idx=i: self._on_flag(idx, new_label)
            )
            flag_opt.grid(row=row, column=4, padx=(6, 4), pady=(2, 2), sticky="w")

            # Acción: Exportar + Borrar
            action_frame = ctk.CTkFrame(self, fg_color="transparent")
            action_frame.grid(row=row, column=5, padx=(6, 4), pady=(2, 2), sticky="w")

            export_btn = ctk.CTkButton(action_frame, text="Exportar", width=60, font=("Segoe UI", 12),
                                       command=lambda idx=i: self._on_export(idx))
            export_btn.pack(side="left", padx=(0, 6))

            del_btn = ctk.CTkButton(
                action_frame, text="🗑", width=40, font=("Segoe UI", 12),
                fg_color="#DC2626", hover_color="#B91C1C",
                command=lambda idx=i: self._on_delete(idx)
            )
            del_btn.pack(side="left", padx=(0, 0))

            self._rows_widgets.append([depth_entry, name_lbl, size_lbl, pct_lbl, slider, flag_opt, export_btn, del_btn])

    # ----- Helpers / Validaciones / Callbacks -----

    def _validate_hex_keystroke(self, proposed: str) -> bool:
        s = proposed.strip()
        if s == "": return True
        if len(s) > 2: return False
        for ch in s:
            if ch not in "0123456789abcdefABCDEF":
                return False
        return True

    def _commit_depth(self, text: str, part_index: int, widget: tk.Widget):
        s = (text or "").strip().upper()
        if s == "": s = "00"
        try: val = int(s, 16)
        except Exception: val = 0
        val = max(0, min(0xFF, val))
        if isinstance(widget, (tk.Entry, ctk.CTkEntry)):
            widget.delete(0, tk.END)
            widget.insert(0, f"{val:02X}")
        if callable(self.on_depth_change):
            self.on_depth_change(part_index, val)

    def _on_opacity(self, value, part_index: int, label_widget: ctk.CTkLabel):
        try: pct = int(round(float(value)))
        except Exception: pct = 0
        pct = max(0, min(100, pct))
        label_widget.configure(text=f"{pct}%")
        if callable(self.on_opacity_change):
            self.on_opacity_change(part_index, pct)

    def _on_flag(self, part_index: int, new_label: str):
        if callable(self.on_flag_change):
            self.on_flag_change(part_index, new_label)

    def _on_export(self, part_index: int):
        if callable(self.on_export_part):
            self.on_export_part(part_index)

    def _on_delete(self, part_index: int):
        if callable(self.on_delete_part):
            self.on_delete_part(part_index)

class SecondaryPartsTable(ctk.CTkScrollableFrame):
    """
    VERSION SOLO LECTURA PARA PMDL SECUNDARIO
    """
    def __init__(self, master, on_add_part):
        super().__init__(master, corner_radius=8)

        # Barra superior
        self._controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._controls_frame.grid(row=0, column=0, columnspan=6, padx=(6, 4), pady=(4, 0), sticky="we")

        self._parts_count_label = ctk.CTkLabel(self._controls_frame, text="Partes: -", font=("Segoe UI", 12))
        self._parts_count_label.pack(side="left", padx=(0, 8))

        # Encabezados (fila 1)
        headers = ["Capa", "Nombre", "Tamaño", "Opacidad", "Función", "Agregar"]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self, text=text, font=("Segoe UI", 12))
            lbl.grid(row=1, column=col, padx=(6, 4), pady=(4, 4), sticky="w")

        # Columnas
        self.grid_columnconfigure(0, weight=0)  # Capa
        self.grid_columnconfigure(1, weight=1)  # Nombre
        self.grid_columnconfigure(2, weight=0)  # Tamaño
        self.grid_columnconfigure(3, weight=0)  # Opacidad
        self.grid_columnconfigure(4, weight=0)  # Función
        self.grid_columnconfigure(5, weight=0)  # Agregar

        self._rows_widgets = []
        self.on_add_part = on_add_part  # callback del padre

    def update_part_count(self, part_count: int):
        self._parts_count_label.configure(text=f"Partes: {part_count}")

    def clear(self):
        for ws in self._rows_widgets:
            for w in ws:
                try: w.destroy()
                except Exception: pass
        self._rows_widgets.clear()

    def populate(self, parts: List[PartIndexEntry]):
        self.clear()
        for i, p in enumerate(parts):
            row = i + 2

            # Capa
            capa_lbl = ctk.CTkLabel(self, text=f"{p.part_id & 0xFF:02X}",
                                    font=("Segoe UI", 12), width=40)
            capa_lbl.grid(row=row, column=0, padx=(6,4), pady=(2,2), sticky="w")

            # Nombre
            name_lbl = ctk.CTkLabel(self, text=f"Parte_{i}", font=("Segoe UI", 12))
            name_lbl.grid(row=row, column=1, padx=(6,4), pady=(2,2), sticky="w")

            # Tamaño
            size_lbl = ctk.CTkLabel(self, text=f"{p.part_length:X}", font=("Segoe UI", 12))
            size_lbl.grid(row=row, column=2, padx=(6,4), pady=(2,2), sticky="w")

            # Opacidad
            if p.opacity <= 0:
                pct = 0
            elif p.opacity >= 0xFFFF:
                pct = 100
            else:
                pct = round(p.opacity * 100 / 0xFFFF)
            pct_lbl = ctk.CTkLabel(self, text=f"{pct}%", font=("Segoe UI", 12))
            pct_lbl.grid(row=row, column=3, padx=(6,4), pady=(2,2), sticky="w")

            # Función
            func_lbl = ctk.CTkLabel(self, text=FLAG_MAP_VALUE_TO_LABEL.get(p.special_flag, "Ninguna"),
                                    font=("Segoe UI", 12))
            func_lbl.grid(row=row, column=4, padx=(6,4), pady=(2,2), sticky="w")

            # Botón Agregar (transfiere esta parte al PMDL principal)
            add_btn = ctk.CTkButton(self, text="Agregar", width=76, font=("Segoe UI", 12),
                                    command=lambda idx=i: self.on_add_part(idx))
            add_btn.grid(row=row, column=5, padx=(6,4), pady=(2,2), sticky="w")

            self._rows_widgets.append([capa_lbl, name_lbl, size_lbl, pct_lbl, func_lbl, add_btn])

class PmdlPartsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry("880x550")
        self.minsize(540, 540)

        # Forzar cálculo real del tamaño
        self.update_idletasks()

        # Centrar ventana
        self.center_window(880, 550)

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

        # === Contenedor principal a dos columnas (izquierda = editor, derecha = visor) ===
        main = ctk.CTkFrame(self, corner_radius=0)
        main.pack(side="top", fill="both", expand=True, padx=6, pady=(6, 4))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # -------- Panel IZQUIERDO (PMDL PRINCIPAL / EDITOR) --------
        left_panel = ctk.CTkFrame(main, corner_radius=8)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        left_panel.grid_rowconfigure(1, weight=1)

        # Barra superior izquierda (ruta + importar + guardar + guardar como)
        top_left = ctk.CTkFrame(left_panel, corner_radius=6)
        top_left.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))

        btn_h = 26
        self.path_entry = ctk.CTkEntry(top_left, placeholder_text="Ruta .pmdl", width=160, font=("Segoe UI", 12), state="disabled")
        self.path_entry.pack(side="left", padx=(6, 4), pady=4)
        # tooltip de ruta completa del archivo
        self.tooltip_path_entry = ToolTip(self.path_entry, "Ruta del archivo PMDL cargado")

        open_btn = ctk.CTkButton(top_left, text="Importar PMDL", width=110, height=btn_h, font=("Segoe UI", 12),
                                 command=self.on_open_file)
        open_btn.pack(side="left", padx=(0, 4), pady=4)

        save_btn = ctk.CTkButton(top_left, text="Guardar", width=80, height=btn_h, font=("Segoe UI", 12),
                                 command=self.on_save)
        save_btn.pack(side="left", padx=(0, 4), pady=4)

        save_as_btn = ctk.CTkButton(top_left, text="Guardar Como", width=120, height=btn_h, font=("Segoe UI", 12),
                                    command=self.on_save_as)
        save_as_btn.pack(side="left", padx=(0, 4), pady=4)

        # Área lista de partes (izquierda)
        mid_left = ctk.CTkFrame(left_panel, corner_radius=8)
        mid_left.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))

        self.parts_table = PartsTable(
            mid_left,
            on_depth_change=self.on_part_depth_changed,
            on_opacity_change=self.on_part_opacity_changed,
            on_flag_change=self.on_part_flag_changed,
            on_export_part=self.on_export_part,
            on_delete_part=self.on_delete_part
        )
        self.parts_table.pack(fill="both", expand=True, padx=8, pady=8)

        # -------- Panel DERECHO (PMDL SECUNDARIO / VISOR) --------
        right_panel = ctk.CTkFrame(main, corner_radius=8)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
        right_panel.grid_rowconfigure(1, weight=1)

        # Barra superior derecha (ruta + importar secundario)
        top_right = ctk.CTkFrame(right_panel, corner_radius=6)
        top_right.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))

        self.path2_entry = ctk.CTkEntry(top_right, placeholder_text="Ruta .pmdl secundario", width=160,
                                        font=("Segoe UI", 12), state="disabled")
        self.path2_entry.pack(side="left", padx=(6, 4), pady=4)
        # tooltip de ruta completa del archivo
        self.tooltip_path2_entry = ToolTip(self.path2_entry, "Ruta del segundo archivo PMDL cargado")

        open2_btn = ctk.CTkButton(top_right, text="Importar PMDL secundario", width=180, height=btn_h, font=("Segoe UI", 12),
                                  command=self.on_open_file_secondary)
        open2_btn.pack(side="left", padx=(0, 4), pady=4)

        # Área lista de partes (derecha, solo lectura)
        mid_right = ctk.CTkFrame(right_panel, corner_radius=8)
        mid_right.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))

        self.parts2_table = SecondaryPartsTable(mid_right, on_add_part=self.on_add_part_from_secondary)
        self.parts2_table.pack(fill="both", expand=True, padx=8, pady=8)

        bottom = ctk.CTkFrame(self, corner_radius=8)
        bottom.pack(side="bottom", fill="x", padx=8, pady=(0, 8))

        self.status_var = tk.StringVar(value="Creado por Los ijue30s")
        status_lbl = ctk.CTkLabel(bottom, textvariable=self.status_var, anchor="w")
        status_lbl.pack(side="left", padx=8, pady=6)

    # ------------ confirmacion para cierre de la app ------------
    def on_close(self):
        if messagebox.askyesno(
                "Salir",
                "¿Estas seguro de que deseas cerrar la aplicacion?"
        ):
            self.destroy()  # Cierra la app

    def center_window(self, width, height):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------ Carga / Render ------------

    def on_open_file(self):
        path = filedialog.askopenfilename(
            title="Selecciona un archivo .pmdl",
            filetypes=[("Pmdl files", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        self._load_and_render(path)

    def _load_and_render(self, path: str):
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

        self.parts_table.show_top_controls(self._hdr.part_count, self.on_import_part)
        self.parts_table.populate(self._parts)
        self.parts_table.show_top_controls(hdr.part_count, self.on_import_part)
        self.status_var.set(f"Archivo cargado: {os.path.basename(path)}")

    # ------------ Ediciones en memoria ------------

    def on_part_depth_changed(self, part_index: int, new_low_byte: int):
        if self._parts and 0 <= part_index < len(self._parts):
            current = self._parts[part_index].part_id
            self._parts[part_index].part_id = (current & 0xFF00) | (new_low_byte & 0x00FF)
            self.status_var.set(f"Parte {part_index:02d}: Profundidad = {new_low_byte:02X}")

    def on_part_opacity_changed(self, part_index: int, new_percent: int):
        if self._parts and 0 <= part_index < len(self._parts):
            self._parts[part_index].opacity = opacity_u16_from_percent(new_percent)
            self.status_var.set(f"Parte {part_index:02d}: Opacidad = {new_percent}%")

    def on_part_flag_changed(self, part_index: int, new_label: str):
        if self._parts and 0 <= part_index < len(self._parts):
            value = FLAG_MAP_LABEL_TO_VALUE.get(new_label, 0x00)
            self._parts[part_index].special_flag = value
            self.status_var.set(f"Parte {part_index:02d}: Función = '{new_label}' (0x{value:02X})")

    # ------------ Exportar parte ------------

    def on_export_part(self, part_index: int):
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        if not (0 <= part_index < len(self._parts)):
            messagebox.showerror("Error", "Índice de parte inválido.")
            return

        p = self._parts[part_index]
        off = p.part_offset
        ln  = p.part_length

        if off < 0 or ln <= 0 or off + ln > len(self._blob):
            messagebox.showerror("Error", f"Rango inválido al exportar (offset={off}, longitud={ln}).")
            return

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

        try:
            chunk = bytes(self._blob[off:off+ln])
            with open(out_path, "wb") as f:
                f.write(chunk)
            messagebox.showinfo("Exportado", f"Parte {part_index:02d} exportada en:\n{out_path}")
            self.status_var.set(f"Parte {part_index:02d} exportada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar la parte:\n{e}")

    def on_delete_part(self, part_index: int):
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return
        if not (0 <= part_index < len(self._parts)):
            messagebox.showerror("Error", "Índice de parte inválido.")
            return

        try:
            # --- Datos base
            index_base = self._hdr.parts_index_offset
            stride = 0x20
            old_count = self._hdr.part_count

            # --- Parte a borrar
            p = self._parts[part_index]
            off = p.part_offset
            ln  = p.part_length

            # (a) Eliminar bytes de la PARTE en el blob
            del self._blob[off:off + ln]

            # (b) Restar longitud 'ln' a offsets de TODAS las partes que estaban DEBAJO
            for j in range(part_index + 1, len(self._parts)):
                self._parts[j].part_offset -= ln

            # (c.1) Eliminar el bloque de índice (0x20) de la parte borrada
            entry_off = index_base + part_index * stride
            del self._blob[entry_off:entry_off + stride]

            # (c.2) Restar 0x20 a offsets de inicio de parte de TODOS los índices
            for j in range(len(self._parts)):
                if j == part_index:
                    continue
                self._parts[j].part_offset -= stride

            # (c.3) Quitar la entrada en memoria
            self._parts.pop(part_index)

            # (d) Decrementar el contador de partes (header @ 0x5C, uint32 LE)
            new_count = old_count - 1
            struct.pack_into("<I", self._blob, 0x5C, new_count)
            self._hdr.part_count = new_count

            # (e) Truncar residuos: al final de la ÚLTIMA parte (si existe)
            if self._hdr.part_count > 0:
                last = self._parts[-1]
                end_of_model = last.part_offset + last.part_length
            else:
                end_of_model = index_base  # sin partes: dejar solo cabecera + índice

            if len(self._blob) > end_of_model:
                del self._blob[end_of_model:]

            # Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)

            # Estado
            self.status_var.set(f"Parte borrada correctamente · Los ijue30s")
            messagebox.showinfo("Borrado", "Parte eliminada correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo borrar la parte:\n{e}")

    # ------------ Guardar ------------

    def on_save(self):
        if self._blob is None or self._hdr is None or not self._parts or not self._path:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return

        # confirmacion antes de escribir em el archivo original
        confirm = messagebox.askyesno(
            "Confirmar guardado",
            "¿Estas seguro de que deseas guardar el archivo?"
        )
        if not confirm:
            return

        self._sync_parts_from_ui()
        base = self._hdr.parts_index_offset
        stride = 0x20
        try:
            for i, p in enumerate(self._parts):
                off = base + i * stride
                # id (H), opacity (H), offset (I), length (I), flag (I)
                struct.pack_into("<H", self._blob, off + 0x00, p.part_id & 0xFFFF)
                struct.pack_into("<H", self._blob, off + 0x02, p.opacity & 0xFFFF)
                struct.pack_into("<I", self._blob, off + 0x04, p.part_offset & 0xFFFFFFFF)
                struct.pack_into("<I", self._blob, off + 0x08, p.part_length & 0xFFFFFFFF)
                struct.pack_into("<I", self._blob, off + 0x0C, p.special_flag & 0xFFFFFFFF)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron aplicar cambios al índice:\n{e}")
            return
        try:
            with open(self._path, "wb") as f:
                f.write(self._blob)
            self.status_var.set("Cambios guardados.")
            messagebox.showinfo("Listo", "Cambios guardados en el .pmdl.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{e}")

    def on_save_as(self):
        if self._blob is None or self._hdr is None or not self._parts:
            messagebox.showinfo("Info", "Abre primero un archivo .pmdl.")
            return

        # Aplicar al buffer los cambios de la tabla al índice de partes
        self._sync_parts_from_ui()
        base = self._hdr.parts_index_offset
        stride = 0x20
        try:
            for i, p in enumerate(self._parts):
                off = base + i * stride
                struct.pack_into("<H", self._blob, off + 0x00, p.part_id & 0xFFFF)
                struct.pack_into("<H", self._blob, off + 0x02, p.opacity & 0xFFFF)
                struct.pack_into("<I", self._blob, off + 0x04, p.part_offset & 0xFFFFFFFF)
                struct.pack_into("<I", self._blob, off + 0x08, p.part_length & 0xFFFFFFFF)
                struct.pack_into("<I", self._blob, off + 0x0C, p.special_flag & 0xFFFFFFFF)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron aplicar cambios al índice:\n{e}")
            return
        # Elegir destino y guardar
        initial = os.path.basename(self._path) if self._path else "nuevo.pmdl"
        out_path = filedialog.asksaveasfilename(
            title="Guardar como...",
            defaultextension=".pmdl",
            initialfile=initial,
            filetypes=[("PMDL", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        if not out_path:
            return

        try:
            with open(out_path, "wb") as f:
                f.write(self._blob)
            self._path = out_path
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, os.path.basename(out_path))
            self.status_var.set(f"Guardado como: {os.path.basename(out_path)}")
            messagebox.showinfo("Listo", f"Guardado como:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _sync_parts_from_ui(self):
        """
        Lee los widgets de la tabla (Capa/ID, Opacidad, Función) y actualiza self._parts.
        Funciona aunque el Entry siga con foco (sin perder cambios al guardar).
        """
        if not hasattr(self.parts_table, "_rows_widgets"):
            return

        for i, ws in enumerate(self.parts_table._rows_widgets):
            try:
                depth_entry = ws[0]
                slider      = ws[4]
                flag_opt    = ws[5]
            except Exception:
                continue

            # --- Capa/ID (HEX 00..FF) ---
            txt = (depth_entry.get() or "").strip().upper()
            if txt == "":
                txt = "00"
            try:
                low = int(txt, 16) & 0xFF
            except Exception:
                low = 0
            current = self._parts[i].part_id
            self._parts[i].part_id = (current & 0xFF00) | low

            # --- Opacidad (slider 0..100 → uint16 0..0xFFFF) ---
            try:
                pct = int(round(float(slider.get())))
            except Exception:
                pct = 0
            pct = max(0, min(100, pct))
            self._parts[i].opacity = opacity_u16_from_percent(pct)

            # --- Función (OptionMenu → etiqueta) ---
            try:
                label = flag_opt.get()
            except Exception:
                label = "Ninguna"
            value = FLAG_MAP_LABEL_TO_VALUE.get(label, 0x00)
            self._parts[i].special_flag = value

    # ------------ Importar Parte (.tttpart) ------------

    def on_import_part(self):
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
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer la .tttpart:\n{e}")
            return

        if not new_part_data:
            messagebox.showerror("Error", "La .tttpart está vacía.")
            return

        try:
            # 1) Insertar un nuevo bloque 0x20 al final del índice
            old_count = self._hdr.part_count
            index_base = self._hdr.parts_index_offset
            index_end_before = index_base + old_count * 0x20
            self._blob[index_end_before:index_end_before] = b"\x00" * 0x20

            # 2) Actualizar 'part_count' en cabecera
            new_count = old_count + 1
            struct.pack_into("<I", self._blob, 0x5C, new_count)
            self._hdr.part_count = new_count

            # 3) Sumar 0x20 a TODOS los offsets de parte existentes (por el corrimiento del índice)
            stride = 0x20
            for i in range(old_count):
                entry_off = index_base + i * stride
                old_off, = struct.unpack_from("<I", self._blob, entry_off + 0x04)
                new_off = old_off + 0x20
                struct.pack_into("<I", self._blob, entry_off + 0x04, new_off)
                self._parts[i].part_offset = new_off

            # 4) Calcular el punto de inserción para los bytes de la nueva parte
            last = self._parts[-1]
            insert_pos = last.part_offset + last.part_length

            # 5) Insertar la parte nueva en los datos
            self._blob[insert_pos:insert_pos] = new_part_data

            # 6) Preparar el nuevo índice
            last_id_low = last.part_id & 0xFF
            new_id_low = min(0xFF, last_id_low + 1)
            new_part_id = (last.part_id & 0xFF00) | new_id_low

            new_opacity = 0xFFFF
            new_flag = 0x00000000
            new_offset = insert_pos
            new_length = len(new_part_data)

            # 7) Escribir el nuevo bloque en el índice
            new_entry_off = index_base + old_count * stride
            struct.pack_into("<H", self._blob, new_entry_off + 0x00, new_part_id & 0xFFFF)
            struct.pack_into("<H", self._blob, new_entry_off + 0x02, new_opacity & 0xFFFF)
            struct.pack_into("<I", self._blob, new_entry_off + 0x04, new_offset & 0xFFFFFFFF)
            struct.pack_into("<I", self._blob, new_entry_off + 0x08, new_length & 0xFFFFFFFF)
            struct.pack_into("<I", self._blob, new_entry_off + 0x0C, new_flag & 0xFFFFFFFF)

            # 8) Actualizar modelo en memoria
            self._parts.append(PartIndexEntry(
                part_id=new_part_id,
                opacity=new_opacity,
                part_offset=new_offset,
                part_length=new_length,
                special_flag=new_flag
            ))

            # 9) TRUNCAR residuos al final del archivo
            end_of_model = new_offset + new_length
            if len(self._blob) > end_of_model:
                trimmed = len(self._blob) - end_of_model
                del self._blob[end_of_model:]
                self.status_var.set(f"Importada y truncada cola: {trimmed} bytes removidos.")
                info_extra = f"\nSe eliminaron {trimmed} bytes residuales."
            else:
                info_extra = ""

            # 10) Refrescar UI
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)
            base = os.path.basename(in_path)
            messagebox.showinfo(
                "Importada",
                f"Parte añadida correctamente.\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}{info_extra}"
            )
            self.parts_table.update_part_count(self._hdr.part_count)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo importar la parte:\n{e}")

    def on_add_part_from_secondary(self, part_index: int):
        # Validaciones básicas
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
            # --- Origen (secundario): datos de la parte a copiar
            src = self._parts2[part_index]
            src_off = src.part_offset
            src_len = src.part_length
            if src_off < 0 or src_len <= 0 or src_off + src_len > len(self._blob2):
                messagebox.showerror("Error", "Rango inválido en la parte del PMDL secundario.")
                return

            src_bytes = bytes(self._blob2[src_off: src_off + src_len])
            src_id    = src.part_id & 0xFFFF
            src_opac  = src.opacity & 0xFFFF
            src_flag  = src.special_flag & 0xFFFFFFFF

            # --- Destino (principal): insertar bloque de índice y ajustar offsets
            index_base = self._hdr.parts_index_offset
            stride = 0x20
            old_count = self._hdr.part_count
            index_end_before = index_base + old_count * stride

            # 1) Inserta 0x20 bytes (nuevo índice) justo al final del índice actual
            self._blob[index_end_before:index_end_before] = b"\x00" * stride

            # 2) Actualiza contador de partes en header (uint32 @ 0x5C)
            new_count = old_count + 1
            struct.pack_into("<I", self._blob, 0x5C, new_count)
            self._hdr.part_count = new_count

            # 3) Suma +0x20 a TODOS los part_offset existentes
            for p in self._parts:
                p.part_offset += stride

            # 4) Punto de inserción de los bytes de la nueva parte
            if old_count > 0:
                last = self._parts[-1]
                insert_pos = last.part_offset + last.part_length
            else:
                # si el modelo sin partes: pega justo después del índice nuevo
                insert_pos = index_base + new_count * stride

            # 5) Inserta bytes de la parte del secundario
            self._blob[insert_pos:insert_pos] = src_bytes

            # 6) Prepara datos del nuevo índice
            new_part_id   = src_id
            new_opacity   = src_opac
            new_flag      = src_flag
            new_offset    = insert_pos
            new_length    = len(src_bytes)

            # 7) Escribe el nuevo bloque de índice (en memoria del blob)
            new_entry_off = index_base + old_count * stride
            struct.pack_into("<H", self._blob, new_entry_off + 0x00, new_part_id & 0xFFFF)
            struct.pack_into("<H", self._blob, new_entry_off + 0x02, new_opacity & 0xFFFF)
            struct.pack_into("<I", self._blob, new_entry_off + 0x04, new_offset & 0xFFFFFFFF)
            struct.pack_into("<I", self._blob, new_entry_off + 0x08, new_length & 0xFFFFFFFF)
            struct.pack_into("<I", self._blob, new_entry_off + 0x0C, new_flag & 0xFFFFFFFF)
            # 0x10..0x1F quedan en cero

            # 8) Actualiza el modelo en memoria (principal)
            self._parts.append(PartIndexEntry(
                part_id=new_part_id,
                opacity=new_opacity,
                part_offset=new_offset,
                part_length=new_length,
                special_flag=new_flag
            ))

            # 9) Truncar residuos al final del archivo
            end_of_model = new_offset + new_length
            if len(self._blob) > end_of_model:
                del self._blob[end_of_model:]

            # 10) Refrescar UI (principal)
            self.parts_table.populate(self._parts)
            self.parts_table.update_part_count(self._hdr.part_count)

            # Mensaje
            self.status_var.set("Parte agregada desde secundario · Los ijue30s")
            messagebox.showinfo(
                "Listo",
                f"Parte agregada desde secundario.\nOffset=0x{new_offset:X}\nLongitud=0x{new_length:X}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo agregar la parte desde el secundario:\n{e}")

    def on_open_file_secondary(self):
        path = filedialog.askopenfilename(
            title="Selecciona un archivo .pmdl (secundario)",
            filetypes=[("Pmdl files", "*.pmdl"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        self._load_and_render_secondary(path)

    def _load_and_render_secondary(self, path: str):
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
        self.parts2_table.update_part_count(self._hdr2.part_count)
        self._path2 = path

        # Mostrar ruta
        self.path2_entry.configure(state="normal")
        self.path2_entry.delete(0, tk.END)
        self.path2_entry.insert(0, os.path.basename(path))
        self.path2_entry.configure(state="disabled")
        self.tooltip_path2_entry.change_text(path)

        # Poblar tabla sólo lectura
        self.parts2_table.populate(self._parts2)

        # Mensaje de estado
        self.status_var.set("PMDL secundario cargado · Los ijue30s")

if __name__ == "__main__":
    app = PmdlPartsApp()
    app.mainloop()
