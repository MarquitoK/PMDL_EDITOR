import os
import struct
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.core.header import parse_header
from app.core.parts_index import parse_parts_index
from app.utils import center_window
from app.utils.icon import set_app_icon
from app.utils.thickness_normalizer import (
    GROSOR_MAXIMO,
    leer_grosor,
    normalizar_pmdl_completo,
)

_FONT_TITLE  = ("Segoe UI", 13, "bold")
_FONT_NORMAL = ("Segoe UI", 12)
_FONT_SMALL  = ("Segoe UI", 11)


class NormalizadorWindow(ctk.CTkToplevel):
    """
    Sub-herramienta para normalizar el grosor de un PMDL.
    Puede recibir el PMDL heredado del editor principal o abrir uno externo.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.title("Normalizador de Grosor")
        self.geometry("340x280")
        self.resizable(False, False)
        center_window(self, 340, 280)
        set_app_icon(self)

        # Estado interno
        self._blob: bytearray | None = None   # datos en memoria
        self._path: str | None = None          # ruta del archivo (solo si es externo)
        self._is_inherited = False             # True = viene del editor principal
        self._display_name = ""

        self._build_ui()

        # Intentar heredar el PMDL del editor principal
        self._try_inherit_from_master()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(self, corner_radius=0)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        # Botón Abrir PMDL
        self.btn_abrir = ctk.CTkButton(
            frame,
            text="📂  Abrir PMDL",
            height=36,
            font=_FONT_NORMAL,
            corner_radius=7,
            fg_color=("#2196F3", "#1976D2"),
            hover_color=("#1976D2", "#1565C0"),
            command=self._on_open_pmdl,
        )
        self.btn_abrir.grid(row=0, column=0, padx=24, pady=(20, 6), sticky="ew")

        # Botón Normalizar
        self.btn_normalizar = ctk.CTkButton(
            frame,
            text="⚡  Normalizar Modelo",
            height=36,
            font=_FONT_NORMAL,
            corner_radius=7,
            state="disabled",
            fg_color=("#FF9800", "#F57C00"),
            hover_color=("#F57C00", "#E65100"),
            command=self._on_normalizar,
        )
        self.btn_normalizar.grid(row=1, column=0, padx=24, pady=6, sticky="ew")

        # Nombre del PMDL
        self.lbl_nombre = ctk.CTkLabel(
            frame,
            text="Sin archivo cargado",
            font=_FONT_SMALL,
            text_color=("gray50", "gray60"),
            anchor="center",
        )
        self.lbl_nombre.grid(row=2, column=0, padx=24, pady=(12, 2), sticky="ew")

        # Estado normalización
        self.lbl_estado = ctk.CTkLabel(
            frame,
            text="",
            font=("Segoe UI", 12, "bold"),
            text_color=("gray50", "gray60"),
            anchor="center",
        )
        self.lbl_estado.grid(row=3, column=0, padx=24, pady=(2, 12), sticky="ew")

        # Botón Guardar (solo para archivos externos)
        self.btn_guardar = ctk.CTkButton(
            frame,
            text="💾  Guardar",
            height=36,
            font=_FONT_NORMAL,
            corner_radius=7,
            fg_color=("#4CAF50", "#388E3C"),
            hover_color=("#388E3C", "#2E7D32"),
            command=self._on_guardar,
        )
        # No se hace grid todavía; se muestra solo cuando corresponde

    # ─────────────────────────────────────────────
    # HERENCIA DEL EDITOR PRINCIPAL
    # ─────────────────────────────────────────────

    def _try_inherit_from_master(self):
        app = self.master
        if not hasattr(app, "_blob") or not app._blob:
            return

        self._blob = bytearray(app._blob)
        self._is_inherited = True
        self._path = None

        # Determinar nombre
        raw_path = getattr(app, "_path", None) or ""
        if raw_path.startswith("[PATCH]"):
            patch_name = os.path.basename(raw_path.replace("[PATCH]", ""))
            self._display_name = f"PMDL de {patch_name}"
        else:
            self._display_name = os.path.basename(raw_path) if raw_path else "PMDL sin nombre"

        self._refresh_ui()

    # ─────────────────────────────────────────────
    # ACCIONES
    # ─────────────────────────────────────────────

    def _on_open_pmdl(self):
        path = filedialog.askopenfilename(
            title="Abrir PMDL",
            filetypes=[("PMDL files", "*.pmdl"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            self._blob = bytearray(data)
            self._path = path
            self._is_inherited = False
            self._display_name = os.path.basename(path)
            self._refresh_ui()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}", parent=self)

    def _on_normalizar(self):
        if not self._blob:
            return

        if self._is_normalizado():
            messagebox.showinfo("Info", "El modelo ya está normalizado.", parent=self)
            return

        try:
            hdr = parse_header(self._blob)
            parts = parse_parts_index(self._blob, hdr)
            normalizar_pmdl_completo(self._blob, hdr.parts_index_offset, parts)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo normalizar:\n{e}", parent=self)
            return

        # Si es heredado, propagar al editor principal
        if self._is_inherited:
            self._push_to_master()

        self._refresh_ui()
        messagebox.showinfo("Listo", "Modelo normalizado correctamente.", parent=self)

    def _on_guardar(self):
        if not self._blob or not self._path:
            return

        resp = messagebox.askyesno(
            "Confirmar",
            f"Se reemplazará el archivo original:\n{self._path}\n\n¿Estás seguro?",
            parent=self,
        )
        if not resp:
            self.destroy()
            return

        try:
            with open(self._path, "wb") as f:
                f.write(self._blob)
            messagebox.showinfo("Guardado", "Archivo guardado correctamente.", parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}", parent=self)

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def _is_normalizado(self) -> bool:
        if not self._blob:
            return False
        try:
            gx, gy, gz = leer_grosor(self._blob)
            return (
                abs(gx - GROSOR_MAXIMO) < 0.01
                and abs(gy - GROSOR_MAXIMO) < 0.01
                and abs(gz - GROSOR_MAXIMO) < 0.01
            )
        except Exception:
            return False

    def _push_to_master(self):
        app = self.master
        if not hasattr(app, "_blob"):
            return
        app._blob = bytearray(self._blob)
        try:
            app._hdr = parse_header(app._blob)
            app._parts = parse_parts_index(app._blob, app._hdr)
        except Exception:
            pass

    def _refresh_ui(self):
        if not self._blob:
            self.lbl_nombre.configure(text="Sin archivo cargado", text_color=("gray50", "gray60"))
            self.lbl_estado.configure(text="", text_color=("gray50", "gray60"))
            self.btn_normalizar.configure(state="disabled")
            self.btn_guardar.grid_remove()
            return

        # Nombre
        self.lbl_nombre.configure(text=self._display_name, text_color=("gray20", "gray80"))

        # Estado
        if self._is_normalizado():
            self.lbl_estado.configure(
                text="✔  PMDL Normalizado",
                text_color=("#2E7D32", "#66BB6A"),
            )
            self.btn_normalizar.configure(state="disabled")
        else:
            self.lbl_estado.configure(
                text="✘  PMDL No normalizado",
                text_color=("#C62828", "#EF5350"),
            )
            self.btn_normalizar.configure(state="normal")

        # Botón guardar: solo si es externo (no heredado)
        if not self._is_inherited and self._path:
            self.btn_guardar.grid(row=4, column=0, padx=24, pady=(0, 20), sticky="ew")
            self.geometry("340x320")
        else:
            self.btn_guardar.grid_remove()
            self.geometry("340x280")
