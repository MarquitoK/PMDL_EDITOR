import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app.core.operations import export_part
from app.logic_sub_parts_pmdl.scrollable_option_menu import ScrollableOptionMenu
from app.logic_sub_parts_pmdl.sub_parts_index import parse_subparts_index
from app.logic_sub_parts_pmdl.operations import calc_subpart_size, export_sub_part

APP_TITLE = "Pmdl Editor - Multi-Select Table"
UI_FONT = ("Segoe UI", 12)
GRID_FONT = ("Consolas", 15)
SEL_COLOR = "#1F538D"
BG_COLOR = "#333333"

class MultiSelectTable(ctk.CTkFrame):
    def __init__(self, master, rows=0, cols=5, headers=None,
                 parent_app=None, path=0, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.parent_app = parent_app
        self.path = path          # 0 = izquierda, 1 = derecha
        self.path_name = None

        self.rows_count = rows
        self.cols_count = cols
        self.cells: list[list[ctk.CTkEntry]] = []
        self.selected_rows: set[int] = set()

        self._build_scroll()
        self._build_headers(headers)

    # =========================
    # UI
    # =========================
    def _build_scroll(self):
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="#2B2B2B",
            corner_radius=0,
            border_width=1,
            border_color="#444444"
        )
        self.scroll.pack(fill="both", expand=True)

    def _build_headers(self, headers):
        if not headers:
            return

        for col, text in enumerate(headers):
            ctk.CTkLabel(
                self.scroll,
                text=text,
                width=75,
                height=30,
                fg_color="#1F1F1F",
                font=("Segoe UI", 12, "bold"),
                corner_radius=0
            ).grid(row=0, column=col, sticky="nsew")

    # =========================
    # HELPERS
    # =========================
    def _get_blob(self):
        return self.parent_app._blob if self.path == 0 else self.parent_app._blob2

    def _get_parts(self):
        return self.parent_app._parts if self.path == 0 else self.parent_app._parts2

    def _get_subparts(self):
        return (
            self.master.master._sub_parts
            if self.path == 0
            else self.master.master._sub_parts2
        )

    def _get_selected_row_index(self):
        if len(self.selected_rows) != 1:
            return None
        return next(iter(self.selected_rows))

    # =========================
    # TABLE CONTROL
    # =========================
    def clear(self):
        for row in self.cells:
            for cell in row:
                cell.destroy()

        self.cells.clear()
        self.selected_rows.clear()
        self.rows_count = 0

        try:
            self.scroll._parent_canvas.yview_moveto(0)
        except AttributeError:
            pass

    def set_table(self, rows=0, subpart=None, part=0):
        self.clear()
        self.rows_count = rows

        data = subpart[part]
        rows_data = [
            [
                e.sub_part,
                e.sub_part_offset,
                e.num_vertices,
                e.num_bones,
                calc_subpart_size(e.num_vertices, e.num_bones),
                e.unk
            ]
            for e in data
        ]

        for r, row_data in enumerate(rows_data):
            widgets = []
            for c in range(self.cols_count):
                entry = self._create_cell(r, c, row_data[c])
                widgets.append(entry)
            self.cells.append(widgets)

        if self.cells:
            self.select_row(0)

    def _create_cell(self, row, col, value):
        entry = ctk.CTkEntry(
            self.scroll,
            width=75,
            height=28,
            font=GRID_FONT,
            justify="center",
            corner_radius=0,
            border_width=1,
            fg_color=BG_COLOR,
            border_color="#444444"
        )

        entry.insert(0, f"{value:02}")
        entry.configure(state="readonly")
        entry.grid(row=row + 1, column=col, sticky="nsew")

        entry.bind("<Button-1>", lambda e, r=row: self._handle_click(e, r))
        entry.bind("<Button-3>", self._open_context_menu)
        return entry

    # =========================
    # SELECTION
    # =========================
    def select_row(self, row_idx: int, scroll_to=True):
        if row_idx < 0 or row_idx >= len(self.cells):
            return

        self.selected_rows = {row_idx}
        self._update_visuals()

        if scroll_to:
            try:
                self.scroll._parent_canvas.yview_moveto(
                    row_idx / max(1, self.rows_count)
                )
            except Exception:
                pass

    def _handle_click(self, event, row_idx):
        ctrl = (event.state & 0x0004) != 0

        if not ctrl:
            self.selected_rows = {row_idx}
        else:
            self.selected_rows.symmetric_difference_update({row_idx})

        self._update_visuals()

    def _update_visuals(self):
        for r, row in enumerate(self.cells):
            color = SEL_COLOR if r in self.selected_rows else BG_COLOR
            for cell in row:
                cell.configure(fg_color=color)

        self._change_labels()

    def get_selected_data(self):
        return [
            [cell.get() for cell in self.cells[r]]
            for r in sorted(self.selected_rows)
        ]

    # =========================
    # CONTEXT MENU
    # =========================
    def _open_context_menu(self, event):
        if not self.selected_rows:
            return

        menu = tk.Menu(
            self,
            tearoff=0,
            bg="#2B2B2B",
            fg="white",
            activebackground=SEL_COLOR
        )

        menu.add_command(
            label="Exportar selecciones",
            command=self._export_subparts
        )

        if self.path == 0:
            menu.add_command(label="Importar Subpart", command=self._import_subparts)
            menu.add_command(label="Insertar Subpart", command=self._insert_subparts)

        menu.tk_popup(event.x_root, event.y_root)

    # =========================
    # OPERATIONS
    # =========================
    def _export_subparts(self):
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return

        try:
            base = os.path.splitext(
                os.path.basename(self.parent_app._path if self.path == 0 else self.parent_app._path2)
            )[0]

            part_idx = (
                self.master.master._index_opt_left
                if self.path == 0
                else self.master.master._index_opt_right
            )

            filename = f"{base}_parte_{part_idx:02}_subparte_{row_idx:02}.tttsubpart"

            out_path = filedialog.asksaveasfilename(
                title="Exportar Subparte",
                defaultextension=".tttsubpart",
                initialfile=filename,
                filetypes=[("TTT SubPart", "*.tttsubpart")]
            )

            if not out_path:
                return

            chunk = export_sub_part(
                self._get_blob(),
                self._get_parts()[part_idx],
                self._get_subparts()[part_idx][row_idx]
            )

            with open(out_path, "wb") as f:
                f.write(chunk)

            messagebox.showinfo("Exportado", f"SubParte {row_idx:02} exportada")
            # self.parent_app.status_var.set(f"SubParte {row_idx:02} exportada.")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _import_subparts(self):
        pass

    def _insert_subparts(self):
        pass

    # =========================
    # PANEL UPDATE
    # =========================
    def _change_labels(self):
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return

        path = self.parent_app._path if self.path == 0 else self.parent_app._path2
        self.path_name = os.path.basename(path) if path else "--"

        ui = self.master.master
        ui.label_name_part.configure(text=f"Pmdl: {self.path_name}")
        ui.label_name_subpart.configure(text=f"SubPart: {row_idx:02}")

        entry = self._get_subparts()[
            ui._index_opt_left if self.path == 0 else ui._index_opt_right
        ][row_idx]

        ui.opt_huesos.set(f"{entry.num_bones:02}")

        for i, e in enumerate(ui.entry_huesos):
            e.delete(0, "end")
            e.insert(0, f"{entry.id_bones[i]:02}")

        ui.entry_unk.delete(0, "end")
        ui.entry_unk.insert(0, str(entry.unk))




class UiSubparts(ctk.CTkToplevel):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.title(APP_TITLE)
        self.geometry("1100x600")

        self.grid_columnconfigure((0, 2), weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=220)
        self.grid_rowconfigure(0, weight=1)

        self._sub_parts = []
        self._sub_parts2 = []

        self._index_opt_left = 0
        self._index_opt_right = 0

        headers = ["N°", "Posicion", "Vertices", "N° huesos", "Size"]

        # =========================
        # CONTENEDOR IZQUIERDO
        # =========================
        self.left_container = ctk.CTkFrame(self, fg_color="transparent")
        self.left_container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.left_container.grid_rowconfigure(1, weight=1)
        self.left_container.grid_columnconfigure(0, weight=1)

        self.opt_left = ScrollableOptionMenu(
            self.left_container,
            values=["Part 0 - Capa: -"],
            width=160,
            command=self.on_left_option_changed,
            name_window=os.path.basename(self.master._path) if self.master._path else "--"
        )
        self.opt_left.grid(row=0, column=0, pady=(0, 10), sticky="w")
        # self.opt_left.set("SubPart 0")

        self.tab_left = MultiSelectTable(
            self.left_container,
            rows=0,
            headers=headers,
            parent_app=self.master
        )
        self.tab_left.grid(row=1, column=0, sticky="nsew")

        # =========================
        # PANEL CENTRAL
        # =========================
        self.panel_mid = ctk.CTkFrame(self, fg_color="transparent")
        self.panel_mid.grid(row=0, column=1, pady=20)

        self.label_name_part = ctk.CTkLabel(
            self.panel_mid,
            text="Part: --",
            font=("Segoe UI", 16, "bold")
        )
        self.label_name_part.pack(pady=10)

        self.label_name_subpart = ctk.CTkLabel(
            self.panel_mid,
            text="SubPart: --",
            font=("Segoe UI", 16, "bold")
        )
        self.label_name_subpart.pack(pady=10)

        self.frame_num_huesos = ctk.CTkFrame(self.panel_mid, fg_color="transparent")
        self.frame_num_huesos.pack(pady=10)

        ctk.CTkLabel(
            self.frame_num_huesos,
            text="N° huesos:",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=(0, 6))

        self.opt_huesos = ctk.CTkOptionMenu(
            self.frame_num_huesos,
            values=["01", "02", "03", "04"],
            width=60
        )
        self.opt_huesos.pack(side="left")
        self.opt_huesos.set("01")

        ctk.CTkLabel(
            self.panel_mid,
            text="IDS",
            font=("Segoe UI", 16, "bold")
        ).pack(pady=10, anchor="w")

        self.frame_huesos = ctk.CTkFrame(self.panel_mid, fg_color="transparent")
        self.frame_huesos.pack(pady=10)

        self.entry_huesos = []
        for i in range(4):
            entry = ctk.CTkEntry(
                self.frame_huesos,
                placeholder_text=f"ID {i + 1}",
                width=35
            )
            entry.pack(side="left", padx=5)
            self.entry_huesos.append(entry)

        self.entry_unk = ctk.CTkEntry(
            self.panel_mid,
            placeholder_text="01 C3 00 12",
            width=80
        )
        self.entry_unk.pack(pady=10)

        self.btn_left_load = ctk.CTkButton(
            self.panel_mid,
            text="Cargar",
            width=100,
            command=self.get_data_subpart
        )
        self.btn_left_load.pack(pady=10)

        self.btn_right_load = ctk.CTkButton(
            self.panel_mid,
            text="Cargar 2",
            width=100,
            command=lambda : self.get_data_subpart(1)
        )
        self.btn_right_load.pack(pady=10)

        # =========================
        # CONTENEDOR DERECHO
        # =========================
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.grid(row=0, column=2, padx=20, pady=20, sticky="nsew")
        self.right_container.grid_rowconfigure(1, weight=1)
        self.right_container.grid_columnconfigure(0, weight=1)

        self.opt_right = ScrollableOptionMenu(
            self.right_container,
            values=["Part 0 - Capa: -"],
            width=160,
            command=self.on_rigth_option_changed,
            name_window=os.path.basename(self.master._path2) if self.master._path2 else "--"
        )
        self.opt_right.grid(row=0, column=0, pady=(0, 10), sticky="w")
        # self.opt_right.set("SubPart 0")

        self.tab_right = MultiSelectTable(
            self.right_container,
            rows=12,
            headers=headers,
            parent_app=self.master,
            path=1
        )
        self.tab_right.grid(row=1, column=0, sticky="nsew")


    def mostrar_info(self):
        datos = self.tab_left.get_selected_data()
        print(f"Filas seleccionadas en Tabla A: {len(datos)}")
        for d in datos:
            print("Fila:", d)

    def get_data_subpart(self, pmdl=0):
        parts_ids = len(self.master._parts if pmdl == 0 else self.master._parts2)
        if parts_ids == 0:
            return

        name_parts = []
        # self._sub_parts = []
        # self._sub_parts2 = []

        for id_part in range(parts_ids):
            data_part = export_part(self.master._blob if pmdl == 0 else self.master._blob2,
                                    self.master._parts[id_part] if pmdl == 0 else self.master._parts2[id_part])

            self._sub_parts.append(parse_subparts_index(data_part)) if pmdl == 0 \
                else self._sub_parts2.append(parse_subparts_index(data_part))

            capa_v = self.master._parts[id_part].part_id if pmdl == 0 else self.master._parts2[id_part].part_id
            name_parts.append(f"Part: {id_part:02} - Capa: {capa_v:02X}")

        if pmdl == 0:
            self.opt_left.configure(values=name_parts)
            self.opt_left.set(name_parts[0])
            self.tab_left.set_table(len(self._sub_parts[0]), self._sub_parts)
        else:
            self.opt_right.configure(values=name_parts)
            self.opt_right.set(name_parts[0])
            self.tab_right.set_table(len(self._sub_parts2[0]), self._sub_parts2)

        # print(self._sub_parts)


    def on_left_option_changed(self, value):
        self._index_opt_left = self.opt_left.values.index(value)

        self.tab_left.set_table(
            len(self._sub_parts[self._index_opt_left]),
            self._sub_parts,
            self._index_opt_left
        )

    def on_rigth_option_changed(self, value):
        self._index_opt_right = self.opt_right.values.index(value)

        self.tab_right.set_table(
            len(self._sub_parts2[self._index_opt_right]),
            self._sub_parts2,
            self._index_opt_right
        )

