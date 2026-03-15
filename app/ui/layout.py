import os
import tkinter as tk
import customtkinter as ctk
from .tables import PartsTable, SecondaryPartsTable
from .tooltip import ToolTip
from app.utils.lang import t


def build_main_layout(parent, callbacks: dict) -> dict:
    main = ctk.CTkFrame(parent, corner_radius=0)
    main.pack(side="top", fill="both", expand=True, padx=6, pady=(6, 4))
    main.grid_columnconfigure(0, weight=6)
    main.grid_columnconfigure(1, weight=4)
    main.grid_rowconfigure(0, weight=1)

    # Panel IZQUIERDO
    left_panel = ctk.CTkFrame(main, corner_radius=8)
    left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
    left_panel.grid_rowconfigure(1, weight=1)
    left_panel.grid_columnconfigure(0, weight=1)

    top_left = ctk.CTkFrame(left_panel, corner_radius=6)
    top_left.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
    top_left.grid_columnconfigure(0, weight=1)

    path_entry = ctk.CTkEntry(top_left, placeholder_text=t("layout.ruta_pmdl"), width=160,
                              font=("Segoe UI", 12), state="disabled")
    path_entry.grid(row=0, column=0, sticky="ew", padx=(6, 4), pady=4)
    tooltip_path_entry = ToolTip(path_entry, t("layout.ruta_pmdl_tooltip"))

    normalize_toggle_var = tk.BooleanVar(value=True)
    normalize_toggle = ctk.CTkSwitch(
        top_left,
        text=t("layout.normalizar_escala"),
        variable=normalize_toggle_var,
        onvalue=True,
        offvalue=False,
        font=("Segoe UI", 11, "bold"),
        progress_color=("#3B8ED0", "#1F6AA5"),
        button_color=("#3B8ED0", "#1F6AA5"),
        button_hover_color=("#5AA0E0", "#2F8AB5")
    )
    normalize_toggle.grid(row=0, column=1, sticky="e", padx=(4, 6), pady=4)
    tooltip_normalize = ToolTip(normalize_toggle, t("layout.normalizar_tooltip"))

    mid_left = ctk.CTkFrame(left_panel, corner_radius=8)
    mid_left.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))

    parts_table = PartsTable(
        mid_left,
        on_depth_change=callbacks['on_part_depth_changed'],
        on_opacity_change=callbacks['on_part_opacity_changed'],
        on_flag_change=callbacks['on_part_flag_changed'],
        on_export_part=callbacks['on_export_part'],
        on_delete_part=callbacks['on_delete_part'],
        on_close_pmdl=callbacks.get('on_close_pmdl_main')
    )
    parts_table.pack(fill="both", expand=True, padx=8, pady=8)

    # Panel DERECHO
    right_panel = ctk.CTkFrame(main, corner_radius=8)
    right_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
    right_panel.grid_rowconfigure(1, weight=1)
    right_panel.grid_columnconfigure(0, weight=1)

    top_right = ctk.CTkFrame(right_panel, corner_radius=6)
    top_right.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))

    path2_entry = ctk.CTkEntry(top_right, placeholder_text=t("layout.ruta_pmdl_sec"),
                               width=160, font=("Segoe UI", 12), state="disabled")
    path2_entry.pack(side="left", padx=(6, 4), pady=4)
    tooltip_path2_entry = ToolTip(path2_entry, t("layout.ruta_pmdl_sec_tooltip"))

    mid_right = ctk.CTkFrame(right_panel, corner_radius=8)
    mid_right.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))

    parts2_table = SecondaryPartsTable(
        mid_right,
        on_add_part=callbacks['on_add_part_from_secondary'],
        on_close_pmdl=callbacks.get('on_close_pmdl_secondary')
    )
    parts2_table.pack(fill="both", expand=True, padx=8, pady=8)

    # Barra de estado
    bottom = ctk.CTkFrame(parent, corner_radius=8)
    bottom.pack(side="bottom", fill="x", padx=8, pady=(0, 8))

    status_var = tk.StringVar(value=t("layout.status_default"))
    status_lbl = ctk.CTkLabel(bottom, textvariable=status_var, anchor="w")
    status_lbl.pack(side="left", padx=8, pady=6)

    return {
        'path_entry': path_entry,
        'tooltip_path_entry': tooltip_path_entry,
        'path2_entry': path2_entry,
        'tooltip_path2_entry': tooltip_path2_entry,
        'parts_table': parts_table,
        'parts2_table': parts2_table,
        'status_var': status_var,
        'normalize_toggle': normalize_toggle,
        'normalize_toggle_var': normalize_toggle_var,
    }