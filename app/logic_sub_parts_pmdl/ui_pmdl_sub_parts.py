import copy
import os
import re
import struct
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app.core.operations import export_part, replace_part
from app.logic_sub_parts_pmdl.scrollable_option_menu import ScrollableOptionMenu
from app.logic_sub_parts_pmdl.sub_parts_index import parse_subparts_index, SubPartIndexEntry
from app.logic_sub_parts_pmdl.operations import calc_subpart_size, export_sub_part, import_sub_part, align_16, \
    insert_sub_part, delete_sub_part

APP_TITLE = "Pmdl Editor - SubParts"
UI_FONT = ("Segoe UI", 12)
GRID_FONT = ("Consolas", 15)
SEL_COLOR = "#1F538D"
BG_COLOR = "#333333"

class MultiSelectTable(ctk.CTkFrame):
    def __init__(self, master, rows=0, cols=5, headers=None,
                 parent_app=None, path=0, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.parent_app = parent_app # clase controllers/app_controller
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
        # return self.parent_app._blob if self.path == 0 else self.parent_app._blob2
        return self.master.master._blobs if self.path == 0 else self.master.master._blobs2

    def _get_parts(self):
        return self.parent_app._parts if self.path == 0 else self.parent_app._parts2

    def _get_subparts(self):
        return (
            self.master.master._sub_parts
            if self.path == 0
            else self.master.master._sub_parts2
        )

    def get_selected_row_indices(self) -> list[int]:
        """
        Devuelve una lista ordenada de filas seleccionadas.
        """
        return sorted(self.selected_rows)

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
            menu.add_command(label="Delete Subpart", command=self._delete_subparts)
        else:
            menu.add_command(label="Agregar selecciones", command=self._add_subparts)

        menu.tk_popup(event.x_root, event.y_root)

    # =========================
    # OPERATIONS
    # =========================
    def _export_subparts(self):
        row_idx = self.get_selected_row_indices()
        if row_idx is None:
            return

        try:
            base = os.path.splitext(
                os.path.basename(self.parent_app._path if self.path == 0 else self.parent_app._path2)
            )[0]

            messagebox.showinfo("Informacion", f"Se exportaran las siguientes subpartes\n{row_idx}\ndel pmdl: {base}")

            part_idx = (
                self.master.master._index_opt_left
                if self.path == 0
                else self.master.master._index_opt_right
            )

            # ==============================
            # exportar un solo archivo
            # ==============================
            if len(row_idx) == 1:
                filename = f"{base}_parte_{part_idx:02}_subparte_{row_idx[0]:02}.tttsubpart"
                out_path = filedialog.asksaveasfilename(
                    title="Exportar Subparte",
                    defaultextension=".tttsubpart",
                    initialfile=filename,
                    filetypes=[("TTT SubPart", "*.tttsubpart")]
                )

                if not out_path:
                    return

                subpart_dat = self._get_subparts()[part_idx][row_idx[0]]
                # datos en bytes de la subparte
                chunk = export_sub_part(
                    self._get_blob(),
                    part_idx,
                    subpart_dat
                )
                dat = bytearray(b'\x00' * 0x10)
                struct.pack_into("<H", dat, 0, subpart_dat.num_vertices)
                struct.pack_into("<H", dat, 2, subpart_dat.num_bones)
                struct.pack_into("<4B", dat, 4, *subpart_dat.id_bones)
                struct.pack_into("<I", dat, 8, subpart_dat.unk)
                chunk = dat + chunk

                with open(out_path, "wb") as f:
                    f.write(chunk)

                messagebox.showinfo("Exportado", f"SubParte {row_idx[0]:02} exportada")
                return

            # ==============================
            # guardar varios archivos
            # ==============================

            out_path = filedialog.askdirectory(
                title="Exportar Subpartes en directorio",
            )

            if not out_path:
                return

            for i in row_idx:
                filename = f"{base}_parte_{part_idx:02}_subparte_{i:02}.tttsubpart"

                subpart_dat = self._get_subparts()[part_idx][i]
                chunk = export_sub_part(
                    self._get_blob(),
                    part_idx,
                    subpart_dat
                )

                dat = bytearray(b'\x00' * 0x10)
                struct.pack_into("<H", dat, 0, subpart_dat.num_vertices)
                struct.pack_into("<H", dat, 2, subpart_dat.num_bones)
                struct.pack_into("<4B", dat, 4, *subpart_dat.id_bones)
                struct.pack_into("<I", dat, 8, subpart_dat.unk)
                chunk = dat + chunk

                with open(Path(out_path, filename), "wb") as f:
                    f.write(chunk)

            messagebox.showinfo("Exportado", f"SubPartes\n{row_idx}\nexportadas")
            # self.parent_app.status_var.set(f"SubParte {row_idx:02} exportada.")

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _import_subparts(self):
        part_idx = self.master.master._index_opt_left

        row_idx = self.get_selected_row_indices()
        if row_idx is None:
            return

        path_subpart = filedialog.askopenfilename(
            title="Importar Subparte",
            initialdir=".",
            filetypes=[("Archivos SubPart", "*.tttsubpart"),
                       ("Todos los archivos", "*.*")]
        )

        if not path_subpart:
            return

        with open(path_subpart, "rb") as f:
            chunk = f.read()
            chunk =  bytearray(chunk)

            # datos de la subparte
            dat_chunk = chunk[:0x10]
            chunk = chunk[0x10:]
            chunk = bytearray(chunk)

        if len(chunk) == 0:
            raise ValueError("La subpart importada esta vacia")

        # blob de las partes en bytes
        blob = self._get_blob()
        part_dat = self._get_subparts()[part_idx][row_idx[0]]
        data_part, cant = import_sub_part(
            blob,
            part_idx,
            part_dat,
            chunk
        )
        # actualizar offset de las subparts
        parts = self._get_subparts()[part_idx]
        for i in range(part_idx + 1, len(parts)):
            parts[i].sub_part_offset+=cant

        # actualizar valores de la subparte
        num_vertices, = struct.unpack_from("<H", dat_chunk,0)
        num_bones, = struct.unpack_from("<H", dat_chunk,2)
        id_bones = list(struct.unpack_from("<4B", dat_chunk, 4))
        unk, = struct.unpack_from("<I", dat_chunk, 8)

        part_dat.num_vertices = num_vertices
        part_dat.num_bones = num_bones
        part_dat.id_bones = id_bones
        part_dat.unk = unk

        # obtener el tamaño de la subparte final
        size_part_end = calc_subpart_size(parts[-1].num_vertices, parts[-1].num_bones)

        # quitar los residuos al final de la parte y alinear a 16
        data_part = data_part[:parts[-1].sub_part_offset + size_part_end]
        align_16(data_part)

        # actualizar el blob dict
        blob[f"{part_idx}"] = data_part

        # añadir los cambios al modelo
        replace_part(self.parent_app._blob, self.parent_app._hdr, self.parent_app._parts, data_part, part_idx)

        messagebox.showinfo("Importado", f"SubParte importada")

    def _insert_subparts(self):
        part_idx = self.master.master._index_opt_left
        row_idx = self.get_selected_row_indices()

        if row_idx is None:
            return
        if len(row_idx) > 1:
            raise ValueError("No se puede insertar si tienes seleccionada mas de una subparte.")

        insert_at = row_idx[0]

        def natural_sort_key(s):
            return [int(t) if t.isdigit() else t.lower()
                    for t in re.split(r'(\d+)', s)]

        paths_subpart = sorted(
            filedialog.askopenfilenames(
                title="Importar Subparte",
                filetypes=[
                    ("Archivos SubPart", "*.tttsubpart"),
                    ("Todos los archivos", "*.*")
                ]
            ),
            key=natural_sort_key
        )

        if not paths_subpart:
            return

        for path_subpart in paths_subpart:
            with open(path_subpart, "rb") as f:
                raw = f.read()
                if not raw:
                    raise ValueError(f"El archivo \"{path_subpart}\" esta vacio")

            raw = bytearray(raw)
            dat_chunk = raw[:0x10]
            chunk = raw[0x10:]  # ya es bytearray por el slice

            # ---- Header de la subparte ----
            num_vertices, = struct.unpack_from("<H", dat_chunk, 0)
            num_bones, = struct.unpack_from("<H", dat_chunk, 2)
            id_bones = list(struct.unpack_from("<4B", dat_chunk, 4))
            unk, = struct.unpack_from("<I", dat_chunk, 8)

            # ---- Inserción binaria ----
            blob = self._get_blob()
            subparts_by_part = self._get_subparts()
            part_dat = subparts_by_part[part_idx][insert_at]

            data_part, cant, offset_insert = insert_sub_part(
                blob,
                part_idx,
                part_dat,
                chunk,
                dat_chunk
            )

            # ---- Actualizar estructura de subpartes ----
            sub_parts = subparts_by_part[part_idx]

            new_entry = SubPartIndexEntry(
                insert_at + 1,
                offset_insert,
                num_vertices,
                num_bones,
                id_bones,
                unk
            )
            sub_parts.insert(insert_at + 1, new_entry)

            # Reindexar IDs y ajustar offsets base (+0x10 del nuevo header)
            for entry in sub_parts:
                entry.sub_part = sub_parts.index(entry)
                entry.sub_part_offset += 0x10

            # Ajustar offsets de los que están después del insert real en el blob
            for i in range(insert_at + 2, len(sub_parts)):
                sub_parts[i].sub_part_offset += cant


            # ---- Alinear y actualizar blob ----
            del data_part[sub_parts[-1].sub_part_offset + calc_subpart_size(sub_parts[-1].num_vertices, sub_parts[-1].num_bones):]
            align_16(data_part)
            blob[str(part_idx)] = data_part

            # print(len(data_part))

            # ---- Reemplazar parte completa en el modelo ----
            replace_part(
                self.parent_app._blob,
                self.parent_app._hdr,
                self.parent_app._parts,
                data_part,
                part_idx
            )

            insert_at+=1

        # ---- Refrescar tabla UI ----
        self.set_table(
            len(self.master.master._sub_parts[part_idx]),
            self.master.master._sub_parts,
            part_idx
        )

        messagebox.showinfo("Insertado", f"SubParte insertada desde la posicion {row_idx[0] + 1:02}\n{paths_subpart}")

    def _add_subparts(self):
        # segundo pmdl
        part_idx_2 = self.master.master._index_opt_right
        row_idx_2 = self.get_selected_row_indices()

        # primer pmdl
        part_idx = self.master.master._index_opt_left
        row_idx = self.master.master.tab_left.get_selected_row_indices()

        if row_idx is None or row_idx_2 is None:
            return

        if len(row_idx) > 1:
            raise ValueError("No se puede agregar si tienes seleccionada mas de una subparte en pmdl 1.")

        insert_at = row_idx[0]

        # datos del pmdl 1
        subparts_by_part =  self.master.master._sub_parts
        blob = self.master.master._blobs

        # datos del pmdl 2
        blob_2 = self._get_blob()
        subparts_by_part_2 = self._get_subparts()

        if not messagebox.askokcancel(
                "Confirmar Agruegar",
                f"Vas a agruegar las siguientes subpartes: {row_idx_2}\n\n¿Deseas continuar?"
        ):
            return

        for subpart_2 in row_idx_2:
            # obtener la subparte del pmdl 2
            part_dat_2 = subparts_by_part_2[part_idx_2][subpart_2]
            raw = export_sub_part(
                blob_2,
                part_idx_2,
                part_dat_2
                )
            raw = bytearray(raw)

            # data chunk y chunk de la subparte a add
            dat_chunk = bytearray(b'\x00' * 0x10)
            struct.pack_into("<H", dat_chunk, 0, part_dat_2.num_vertices)
            struct.pack_into("<H", dat_chunk, 2, part_dat_2.num_bones)
            struct.pack_into("<4B", dat_chunk, 4, *part_dat_2.id_bones)
            struct.pack_into("<I", dat_chunk, 8, part_dat_2.unk)
            chunk = raw

            # ---- Header de la subparte ----
            num_vertices, = struct.unpack_from("<H", dat_chunk, 0)
            num_bones, = struct.unpack_from("<H", dat_chunk, 2)
            id_bones = list(struct.unpack_from("<4B", dat_chunk, 4))
            unk, = struct.unpack_from("<I", dat_chunk, 8)

            # ---- Inserción binaria ----
            part_dat = subparts_by_part[part_idx][insert_at]
            data_part, cant, offset_insert = insert_sub_part(
                blob,
                part_idx,
                part_dat,
                chunk,
                dat_chunk
            )

            # ---- Actualizar estructura de subpartes ----
            sub_parts = subparts_by_part[part_idx]

            new_entry = SubPartIndexEntry(
                insert_at + 1,
                offset_insert,
                num_vertices,
                num_bones,
                id_bones,
                unk
            )
            sub_parts.insert(insert_at + 1, new_entry)

            # Reindexar IDs y ajustar offsets base (+0x10 del nuevo header)
            for entry in sub_parts:
                entry.sub_part = sub_parts.index(entry)
                entry.sub_part_offset += 0x10

            # Ajustar offsets de los que están después del insert real en el blob
            for i in range(insert_at + 2, len(sub_parts)):
                sub_parts[i].sub_part_offset += cant


            # ---- Alinear y actualizar blob ----
            del data_part[sub_parts[-1].sub_part_offset + calc_subpart_size(sub_parts[-1].num_vertices, sub_parts[-1].num_bones):]
            align_16(data_part)
            blob[str(part_idx)] = data_part

            # print(len(data_part))

            # ---- Reemplazar parte completa en el modelo ----
            replace_part(
                self.parent_app._blob,
                self.parent_app._hdr,
                self.parent_app._parts,
                data_part,
                part_idx
            )

            insert_at+=1

        # ---- Refrescar tabla UI ----
        self.master.master.tab_left.set_table(
            len(self.master.master._sub_parts[part_idx]),
            self.master.master._sub_parts,
            part_idx
        )

        messagebox.showinfo("Agruegada", f"SubParte agruegada desde la posicion {row_idx[0] + 1:02}")


    def _delete_subparts(self):
        band = False
        part_idx = self.master.master._index_opt_left
        row_idx = self.get_selected_row_indices()
        row_idx_old = copy.deepcopy(row_idx)

        if not messagebox.askokcancel(
                "Confirmar eliminación",
                f"Vas a eliminar las siguientes subpartes: {row_idx}\n\n¿Deseas continuar?"
        ):
            return

        try:
            for index_row in range(len(row_idx)):
                blob = self._get_blob()
                subparts_by_part = self._get_subparts()

                if band:
                    for cor in range(len(row_idx)):
                        row_idx[cor]-=1
                band = True

                subpart_dat = subparts_by_part[part_idx][row_idx[index_row]]

                data_part, cant = delete_sub_part(blob, part_idx, subpart_dat)

                # eliminar datos de la subpart
                del subparts_by_part[part_idx][subpart_dat.sub_part]

                # arreglar offsets
                for i in range(len(subparts_by_part[part_idx])):
                    subparts_by_part[part_idx][i].sub_part_offset -= 0x10
                    subparts_by_part[part_idx][i].sub_part = i

                for i in range(subpart_dat.sub_part, len(subparts_by_part[part_idx])):
                    subparts_by_part[part_idx][i].sub_part_offset -= cant

                # ---- Alinear y actualizar blob ----
                del data_part[subparts_by_part[part_idx][-1].sub_part_offset + calc_subpart_size(subparts_by_part[part_idx][-1].num_vertices,
                                                                                       subparts_by_part[part_idx][-1].num_bones):]
                align_16(data_part)
                blob[str(part_idx)] = data_part

                # ---- Reemplazar parte completa en el modelo ----
                replace_part(
                    self.parent_app._blob,
                    self.parent_app._hdr,
                    self.parent_app._parts,
                    data_part,
                    part_idx
                )

            # ---- Refrescar tabla UI ----
            self.set_table(
                len(self.master.master._sub_parts[part_idx]),
                self.master.master._sub_parts,
                part_idx
            )

            messagebox.showinfo("Elimanado", f"SubPartes {row_idx_old} eliminadas correctamente")
        except Exception as e:

            messagebox.showerror(
                "Error",
                f"Ocurrió un problema al eliminar las subpartes.\n{e}"
            )

    # =========================
    # PANEL UPDATE
    # =========================
    def _change_labels(self):
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return

        path = self.parent_app._path if self.path == 0 else self.parent_app._path2
        self.path_name = os.path.basename(path) if path else "--"

        ui = self.master.master # clase UiSubparts
        ui.label_name_part.configure(text=f"Pmdl: {self.path_name}")
        ui.label_name_subpart.configure(text=f"SubPart: {row_idx:02}")

        entry = self._get_subparts()[
            ui._index_opt_left if self.path == 0 else ui._index_opt_right
        ][row_idx]

        ui.opt_huesos.set(f"{entry.num_bones:02}")
        ui.on_huesos_changed(f"{entry.num_bones:02}")

        for i, e in enumerate(ui.entry_huesos):
            e.delete(0, "end")
            e.insert(0, f"{entry.id_bones[i]:02}")

        ui.entry_unk.delete(0, "end")
        ui.entry_unk.insert(0, str(entry.unk))




class UiSubparts(ctk.CTkToplevel):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.title(APP_TITLE)
        self.geometry("1200x600")

        self.grid_columnconfigure((0, 2), weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=220)
        self.grid_rowconfigure(0, weight=1)

        self._sub_parts = []
        self._sub_parts2 = []

        self._blobs = {}
        self._blobs2 = {}

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
        # PANEL CENTRAL (MEJORADO)
        # =========================
        self.panel_mid = ctk.CTkFrame(
            self,
            fg_color="#242424",
            corner_radius=12
        )
        self.panel_mid.grid(row=0, column=1, padx=10, pady=20, sticky="n")
        self.panel_mid.grid_columnconfigure(0, weight=1)

        # ========= HEADER =========
        header = ctk.CTkFrame(self.panel_mid, fg_color="transparent")
        header.grid(row=0, column=0, pady=(10, 15))

        self.label_name_part = ctk.CTkLabel(
            header,
            text="Pmdl: --",
            font=("Segoe UI", 16, "bold")
        )
        self.label_name_part.pack()

        self.label_name_subpart = ctk.CTkLabel(
            header,
            text="SubPart: --",
            font=("Segoe UI", 14)
        )
        self.label_name_subpart.pack()

        # ========= CARD CONFIG =========
        card_cfg = ctk.CTkFrame(
            self.panel_mid,
            fg_color="#2B2B2B",
            corner_radius=10
        )
        card_cfg.grid(row=1, column=0, padx=15, pady=10, sticky="ew")
        card_cfg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_cfg,
            text="Configuración",
            font=("Segoe UI", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=(8, 12))

        # N° huesos
        ctk.CTkLabel(
            card_cfg,
            text="N° huesos:",
            font=("Segoe UI", 13)
        ).grid(row=1, column=0, sticky="w", padx=10)

        self.opt_huesos = ctk.CTkOptionMenu(
            card_cfg,
            values=["01", "02", "03", "04"],
            width=70,
            command=self.on_huesos_changed
        )
        self.opt_huesos.grid(row=1, column=1, sticky="e", padx=10)
        self.opt_huesos.set("01")

        # IDS
        ctk.CTkLabel(
            card_cfg,
            text="IDs:",
            font=("Segoe UI", 13)
        ).grid(row=2, column=0, sticky="nw", padx=10, pady=(10, 0))

        ids_frame = ctk.CTkFrame(card_cfg, fg_color="transparent")
        ids_frame.grid(row=2, column=1, sticky="e", padx=10, pady=(10, 0))

        self.entry_huesos = []
        for i in range(4):
            entry = ctk.CTkEntry(
                ids_frame,
                placeholder_text=f"{i + 1}",
                width=38,
                justify="center"
            )
            entry.pack(side="left", padx=3)
            self.entry_huesos.append(entry)

        # UNK
        ctk.CTkLabel(
            card_cfg,
            text="UNK:",
            font=("Segoe UI", 13)
        ).grid(row=3, column=0, sticky="w", padx=10, pady=10)

        self.entry_unk = ctk.CTkEntry(
            card_cfg,
            placeholder_text="01 C3 00 12",
            width=110
        )
        self.entry_unk.grid(row=3, column=1, sticky="e", padx=10, pady=10)

        # ========= CARD ACTIONS =========
        card_actions = ctk.CTkFrame(
            self.panel_mid,
            fg_color="#2B2B2B",
            corner_radius=10
        )
        card_actions.grid(row=2, column=0, padx=15, pady=10, sticky="ew")
        card_actions.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card_actions,
            text="Acciones",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(8, 12))

        self.btn_left_load = ctk.CTkButton(
            card_actions,
            text="Mover arriba",
            width=120,
            command=self.get_data_subpart
        )
        self.btn_left_load.pack(pady=5)

        self.btn_right_load = ctk.CTkButton(
            card_actions,
            text="Mover abajo",
            width=120,
            command=lambda: self.get_data_subpart(1)
        )
        self.btn_right_load.pack(pady=(0, 10))

        self.btn_save_part = ctk.CTkButton(
            card_actions,
            text="Guardar cambios",
            width=120,
            command=self.on_save_part
        )
        self.btn_save_part.pack(pady=(0, 10))

        self.btn_ui_pmdl_editor = ctk.CTkButton(
            card_actions,
            text="Regresar",
            width=120,
            command=self.on_back
        )
        self.btn_ui_pmdl_editor.pack(pady=(0, 10))

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

            if pmdl == 0:
                self._sub_parts.append(parse_subparts_index(data_part))
                self._blobs[f"{id_part}"] = data_part
            else:
                self._sub_parts2.append(parse_subparts_index(data_part))
                self._blobs2[f"{id_part}"] = data_part

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

    def on_huesos_changed(self, value: str):
        for i in range(4):
            if i < int(value):
                self.entry_huesos[i].pack(side="left", padx=3)
            else:
                self.entry_huesos[i].pack_forget()

    def on_save_part(self):
        try:
            # guardar la id de la parte actual
            id_part = self._index_opt_left

            # datos de la parte en bytes
            part_data = self._sub_parts[0][id_part].blob_subpart
            replace_part(self.master._blob, self.master._hdr, self.master._parts, part_data, id_part)

            messagebox.showinfo("Guardado", f"cambios guardados en ememorio")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_back(self):
        self.master.on_open_pmdl_editor()
        self.withdraw()
        self.destroy()