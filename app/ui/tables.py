import tkinter as tk
import customtkinter as ctk
from typing import List, Callable
from app.core import PartIndexEntry, FLAG_MAP_VALUE_TO_LABEL


class PartsTable(ctk.CTkScrollableFrame):
    """Tabla editable para el PMDL principal."""
    
    def __init__(self, master, on_depth_change: Callable, on_opacity_change: Callable,
                 on_flag_change: Callable, on_export_part: Callable, on_delete_part: Callable):
        super().__init__(master, corner_radius=8)
        
        self.on_depth_change = on_depth_change
        self.on_opacity_change = on_opacity_change
        self.on_flag_change = on_flag_change
        self.on_export_part = on_export_part
        self.on_delete_part = on_delete_part
        
        # Estado UI
        self._rows_widgets = []
        self._row_backgrounds = []  # Para zebra striping
        self._controls_frame = None
        self._parts_count_label = None
        self._top_import_btn = None
        self._close_btn = None
        
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
        
        # Validación para campo hex (Capa)
        self._vcmd = (self.register(self._validate_hex_keystroke), "%P")
    
    def show_top_controls(self, part_count: int, on_import_part_cb: Callable):
        """Muestra los controles superiores (contador, botones)."""
        if self._controls_frame is not None:
            try:
                self._controls_frame.destroy()
            except Exception:
                pass
            self._controls_frame = None
            self._parts_count_label = None
            self._top_import_btn = None
            self._close_btn = None
        
        self._controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._controls_frame.grid(row=0, column=0, columnspan=6, padx=(6, 4), pady=(4, 0), sticky="we")
        
        # Contador de partes (a la izquierda)
        self._parts_count_label = ctk.CTkLabel(
            self._controls_frame, text=f"Partes: {part_count}", font=("Segoe UI", 12)
        )
        self._parts_count_label.pack(side="left", padx=(0, 8))
        
        # Botón Importar Parte (después del contador)
        self._top_import_btn = ctk.CTkButton(
            self._controls_frame, text="Importar Parte", width=120, height=24,
            font=("Segoe UI", 12), command=on_import_part_cb
        )
        self._top_import_btn.pack(side="left", padx=(0, 8))
        
        # Botón Cerrar PMDL (después de Importar Parte)
        self._close_btn = ctk.CTkButton(
            self._controls_frame, text="Cerrar PMDL", width=100, height=24,
            font=("Segoe UI", 12), fg_color="#DC2626", hover_color="#B91C1C",
            command=self._on_close_pmdl
        )
        self._close_btn.pack(side="left", padx=(0, 0))
    
    def hide_top_controls(self):
        """Oculta los controles superiores."""
        if self._controls_frame is not None:
            try:
                self._controls_frame.destroy()
            except Exception:
                pass
            self._controls_frame = None
            self._parts_count_label = None
            self._top_import_btn = None
            self._close_btn = None
    
    def update_part_count(self, part_count: int):
        """Actualiza el contador de partes."""
        if self._parts_count_label is not None:
            self._parts_count_label.configure(text=f"Partes: {part_count}")
    
    def clear(self):
        """Limpia todas las filas de la tabla."""
        for ws in self._rows_widgets:
            for w in ws:
                try:
                    w.destroy()
                except Exception:
                    pass
        self._rows_widgets.clear()
        
        # Limpiar backgrounds de zebra striping
        for bg in self._row_backgrounds:
            try:
                bg.destroy()
            except Exception:
                pass
        self._row_backgrounds.clear()
    
    def populate(self, parts: List[PartIndexEntry]):
        """Puebla la tabla con las partes del PMDL."""
        self.clear()
        
        for i, p in enumerate(parts):
            row = i + 2
            
            # Zebra striping - colores alternados para mejor legibilidad
            is_even = i % 2 == 0
            bg_color = ("gray85", "gray20") if is_even else ("gray90", "gray17")
            
            # Frame de fondo para la fila (zebra striping)
            row_bg = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=0, height=28)
            row_bg.grid(row=row, column=0, columnspan=6, sticky="ew", padx=0, pady=0)
            self._row_backgrounds.append(row_bg)
            
            # Capa
            depth_hex = f"{p.part_id & 0xFF:02X}"
            depth_entry = ctk.CTkEntry(self, width=56, justify="center", font=("Segoe UI", 12), fg_color=bg_color)
            depth_entry.insert(0, depth_hex)
            depth_entry.configure(validate="key", validatecommand=self._vcmd)
            depth_entry.bind("<FocusOut>", lambda e, idx=i: self._commit_depth(e.widget.get(), idx, e.widget))
            depth_entry.bind("<Return>", lambda e, idx=i: self._commit_depth(e.widget.get(), idx, e.widget))
            depth_entry.grid(row=row, column=0, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Nombre
            name_lbl = ctk.CTkLabel(self, text=f"Parte_{i}", font=("Segoe UI", 12), fg_color=bg_color)
            name_lbl.grid(row=row, column=1, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Tamaño
            size_lbl = ctk.CTkLabel(self, text=f"{p.part_length:X}", font=("Segoe UI", 12), fg_color=bg_color)
            size_lbl.grid(row=row, column=2, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Opacidad
            if p.opacity <= 0:
                pct = 0
            elif p.opacity >= 0xFFFF:
                pct = 100
            else:
                pct = round(p.opacity * 100 / 0xFFFF)
            
            pct_lbl = ctk.CTkLabel(self, text=f"{pct}%", width=36, font=("Segoe UI", 12), fg_color=bg_color)
            pct_lbl.grid(row=row, column=3, padx=(6, 2), pady=(2, 2), sticky="w")
            
            slider = ctk.CTkSlider(self, from_=0, to=100, number_of_steps=100, width=60, height=10, fg_color=bg_color)
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
                width=100,
                font=("Segoe UI", 12),
                state="readonly",
                fg_color=bg_color,
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
    
    def get_ui_data(self) -> List[dict]:
        """Obtiene los datos actuales de la UI."""
        data = []
        for ws in self._rows_widgets:
            try:
                depth_entry = ws[0]
                slider = ws[4]
                flag_opt = ws[5]
                
                # Depth
                txt = (depth_entry.get() or "").strip().upper()
                if txt == "":
                    txt = "00"
                try:
                    depth = int(txt, 16) & 0xFF
                except Exception:
                    depth = 0
                
                # Opacity
                try:
                    opacity_pct = int(round(float(slider.get())))
                except Exception:
                    opacity_pct = 100
                
                # Flag
                try:
                    flag_label = flag_opt.get()
                except Exception:
                    flag_label = "Ninguna"
                
                data.append({
                    'depth': depth,
                    'opacity_pct': opacity_pct,
                    'flag_label': flag_label
                })
            except Exception:
                continue
        
        return data
    
    # ----- Helpers / Validaciones / Callbacks -----
    
    def _validate_hex_keystroke(self, proposed: str) -> bool:
        """Valida entrada hexadecimal."""
        s = proposed.strip()
        if s == "":
            return True
        if len(s) > 2:
            return False
        for ch in s:
            if ch not in "0123456789abcdefABCDEF":
                return False
        return True
    
    def _commit_depth(self, text: str, part_index: int, widget: tk.Widget):
        """Confirma el cambio de profundidad."""
        s = (text or "").strip().upper()
        if s == "":
            s = "00"
        try:
            val = int(s, 16)
        except Exception:
            val = 0
        val = max(0, min(0xFF, val))
        
        if isinstance(widget, (tk.Entry, ctk.CTkEntry)):
            widget.delete(0, tk.END)
            widget.insert(0, f"{val:02X}")
        
        if callable(self.on_depth_change):
            self.on_depth_change(part_index, val)
    
    def _on_opacity(self, value, part_index: int, label_widget: ctk.CTkLabel):
        """Callback de cambio de opacidad."""
        try:
            pct = int(round(float(value)))
        except Exception:
            pct = 0
        pct = max(0, min(100, pct))
        label_widget.configure(text=f"{pct}%")
        
        if callable(self.on_opacity_change):
            self.on_opacity_change(part_index, pct)
    
    def _on_flag(self, part_index: int, new_label: str):
        """Callback de cambio de función."""
        if callable(self.on_flag_change):
            self.on_flag_change(part_index, new_label)
    
    def _on_export(self, part_index: int):
        """Callback de exportación."""
        if callable(self.on_export_part):
            self.on_export_part(part_index)
    
    def _on_delete(self, part_index: int):
        """Callback de eliminación."""
        if callable(self.on_delete_part):
            self.on_delete_part(part_index)
    
    def _on_close_pmdl(self):
        """Callback para cerrar el PMDL."""
        from tkinter import messagebox
        if messagebox.askyesno("Cerrar PMDL", "¿Estás seguro de que deseas cerrar el PMDL principal?\nSe perderán todos los cambios no guardados."):
            # Llamar al método del controlador para limpiar todo
            if hasattr(self.master, 'master') and hasattr(self.master.master, 'on_close_pmdl_main'):
                self.master.master.on_close_pmdl_main()


class SecondaryPartsTable(ctk.CTkScrollableFrame):
    """Tabla de solo lectura para PMDL secundario."""
    
    def __init__(self, master, on_add_part: Callable):
        super().__init__(master, corner_radius=8)
        
        self.on_add_part = on_add_part
        
        # Barra superior
        self._controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._controls_frame.grid(row=0, column=0, columnspan=6, padx=(6, 4), pady=(4, 0), sticky="we")
        
        # Contador de partes
        self._parts_count_label = ctk.CTkLabel(self._controls_frame, text="Partes: -", font=("Segoe UI", 12))
        self._parts_count_label.pack(side="left", padx=(0, 8))
        
        # Botón Cerrar PMDL Secundario
        self._close_btn = ctk.CTkButton(
            self._controls_frame, text="Cerrar PMDL", width=100, height=24,
            font=("Segoe UI", 12), fg_color="#DC2626", hover_color="#B91C1C",
            command=self._on_close_pmdl_secondary
        )
        self._close_btn.pack(side="left", padx=(0, 0))
        
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
        self._row_backgrounds = []  # Para zebra striping
    
    def update_part_count(self, part_count: int):
        """Actualiza el contador de partes."""
        self._parts_count_label.configure(text=f"Partes: {part_count}")
    
    def clear(self):
        """Limpia todas las filas de la tabla."""
        for ws in self._rows_widgets:
            for w in ws:
                try:
                    w.destroy()
                except Exception:
                    pass
        self._rows_widgets.clear()
        
        # Limpiar backgrounds de zebra striping
        for bg in self._row_backgrounds:
            try:
                bg.destroy()
            except Exception:
                pass
        self._row_backgrounds.clear()
    
    def populate(self, parts: List[PartIndexEntry]):
        """Puebla la tabla con las partes del PMDL secundario."""
        self.clear()
        
        for i, p in enumerate(parts):
            row = i + 2
            
            # Zebra striping - colores alternados para mejor legibilidad
            is_even = i % 2 == 0
            bg_color = ("gray85", "gray20") if is_even else ("gray90", "gray17")
            
            # Frame de fondo para la fila (zebra striping)
            row_bg = ctk.CTkFrame(self, fg_color=bg_color, corner_radius=0, height=28)
            row_bg.grid(row=row, column=0, columnspan=6, sticky="ew", padx=0, pady=0)
            self._row_backgrounds.append(row_bg)
            
            # Capa
            capa_lbl = ctk.CTkLabel(self, text=f"{p.part_id & 0xFF:02X}",
                                    font=("Segoe UI", 12), width=40, fg_color=bg_color)
            capa_lbl.grid(row=row, column=0, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Nombre
            name_lbl = ctk.CTkLabel(self, text=f"Parte_{i}", font=("Segoe UI", 12), fg_color=bg_color)
            name_lbl.grid(row=row, column=1, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Tamaño
            size_lbl = ctk.CTkLabel(self, text=f"{p.part_length:X}", font=("Segoe UI", 12), fg_color=bg_color)
            size_lbl.grid(row=row, column=2, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Opacidad
            if p.opacity <= 0:
                pct = 0
            elif p.opacity >= 0xFFFF:
                pct = 100
            else:
                pct = round(p.opacity * 100 / 0xFFFF)
            pct_lbl = ctk.CTkLabel(self, text=f"{pct}%", font=("Segoe UI", 12), fg_color=bg_color)
            pct_lbl.grid(row=row, column=3, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Función
            func_lbl = ctk.CTkLabel(self, text=FLAG_MAP_VALUE_TO_LABEL.get(p.special_flag, "Ninguna"),
                                    font=("Segoe UI", 12), fg_color=bg_color)
            func_lbl.grid(row=row, column=4, padx=(6, 4), pady=(2, 2), sticky="w")
            
            # Botón Agregar
            add_btn = ctk.CTkButton(self, text="Agregar", width=76, font=("Segoe UI", 12),
                                    command=lambda idx=i: self.on_add_part(idx))
            add_btn.grid(row=row, column=5, padx=(6, 4), pady=(2, 2), sticky="w")
            
            self._rows_widgets.append([capa_lbl, name_lbl, size_lbl, pct_lbl, func_lbl, add_btn])
    
    def _on_close_pmdl_secondary(self):
        """Callback para cerrar el PMDL secundario."""
        from tkinter import messagebox
        if messagebox.askyesno("Cerrar PMDL Secundario", "¿Estás seguro de que deseas cerrar el PMDL secundario?"):
            # Llamar al método del controlador para limpiar todo
            if hasattr(self.master, 'master') and hasattr(self.master.master, 'on_close_pmdl_secondary'):
                self.master.master.on_close_pmdl_secondary()