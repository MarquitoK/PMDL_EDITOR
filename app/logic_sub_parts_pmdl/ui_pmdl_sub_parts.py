import copy
import os
import re
import struct
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app.core.operations import export_part, replace_part
from app.logic_sub_parts_pmdl.header_subpart import SpartHeader, comprobar_header_spart
from app.logic_sub_parts_pmdl.options_subparts import RemapBones
from app.logic_sub_parts_pmdl.scrollable_option_menu import ScrollableOptionMenu
from app.logic_sub_parts_pmdl.sub_parts_index import parse_subparts_index, SubPartIndexEntry
from app.logic_sub_parts_pmdl.operations import calc_subpart_size, export_sub_part, import_sub_part, align_16, \
    insert_sub_part, delete_sub_part, move_up, split_fixed, bones_strip, replace_id_ff
from app.logic_sub_parts_pmdl.ui_edit_vertex import VertexEditor
from app.ui import ToolTip
from app.utils import center_window
from app.utils.icon import set_app_icon
from app.utils.thickness_normalizer import normalizar_pmdl_completo, preparar_parte_externa_para_insercion, leer_grosor, \
    normalizar_subparte
from app.utils.ui_error_window import error_window_ui
import app.utils.lang as lang
from app.utils.lang import t

APP_TITLE = t("ui_subparts.titulo")
UI_FONT = ("Segoe UI", 12)
GRID_FONT = ("Consolas", 15)
SEL_COLOR = "#1F538D"
BG_COLOR = "#333333"
BG_COLOR_ALT = "#2E2E2E"

class MultiSelectTable(ctk.CTkFrame):

    def __init__(self, master, rows=0, cols=5, headers=None,
                 parent_app=None, path=0, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.parent_app = parent_app
        self.path = path
        self.path_name = None

        self.anchor_row: int | None = None

        self.rows_count = rows
        self.cols_count = cols

        self.cells: list[list[ctk.CTkEntry]] = []
        self.selected_rows: set[int] = set()
        self._last_selected_rows: set[int] = set()

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
        self._last_selected_rows.clear()

        self.rows_count = 0

        try:
            self.scroll._parent_canvas.yview_moveto(0)
        except AttributeError:
            pass

    def set_table(self, rows=0, subpart=None, part=0):

        self.clear()
        self.rows_count = rows

        data = subpart[part]

        for r, e in enumerate(data):

            values = (
                e.sub_part,
                e.sub_part_offset,
                e.num_vertices,
                e.num_bones,
                calc_subpart_size(e.num_vertices, e.num_bones),
                e.unk
            )

            widgets = []

            for c, value in enumerate(values):

                entry = self._create_cell(r, c, value)
                widgets.append(entry)

            self.cells.append(widgets)

        if self.cells:
            self.select_row(0)

        self.scroll.update_idletasks()

    def _create_cell(self, row, col, value):

        var = tk.StringVar(value=f"{value:02}")

        row_color = BG_COLOR if row % 2 == 0 else BG_COLOR_ALT

        entry = ctk.CTkEntry(
            self.scroll,
            textvariable=var,
            width=75,
            height=28,
            font=GRID_FONT,
            justify="center",
            corner_radius=0,
            border_width=1,
            fg_color=row_color,
            border_color="#444444",
            state="readonly"
        )

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
        self.anchor_row = row_idx

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
        shift = (event.state & 0x0001) != 0

        if shift:

            if self.anchor_row is None:
                self.anchor_row = row_idx

            start = min(self.anchor_row, row_idx)
            end = max(self.anchor_row, row_idx)

            self.selected_rows.update(range(start, end + 1))

        elif ctrl:

            if row_idx in self.selected_rows:
                self.selected_rows.remove(row_idx)
            else:
                self.selected_rows.add(row_idx)

            self.anchor_row = row_idx

        else:

            self.selected_rows = {row_idx}
            self.anchor_row = row_idx

        self._update_visuals()

    def _update_visuals(self):

        changed = self.selected_rows ^ self._last_selected_rows

        for r in changed:

            if r >= len(self.cells):
                continue

            if r in self.selected_rows:
                color = SEL_COLOR
            else:
                color = BG_COLOR if r % 2 == 0 else BG_COLOR_ALT

            for cell in self.cells[r]:
                cell.configure(fg_color=color)

        self._last_selected_rows = set(self.selected_rows)

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
            label=t('ui_subparts.ctx_export'),
            command=self._export_subparts
        )

        if self.path == 0:
            menu.add_command(label=t('ui_subparts.ctx_import'), command=self._import_subparts)
            menu.add_command(label=t('ui_subparts.ctx_insert'), command=self._insert_subparts)
            menu.add_command(label=t('ui_subparts.ctx_delete'), command=self._delete_subparts)
        else:
            menu.add_command(label=t('ui_subparts.ctx_add'), command=self._add_subparts)

        menu.tk_popup(event.x_root, event.y_root)


    # =========================
    # OPERATIONS
    # =========================
    @error_window_ui
    def _export_subparts(self):
        row_idx = self.get_selected_row_indices()
        if row_idx is None:
            return

        base = os.path.splitext(
            os.path.basename(self.parent_app._path if self.path == 0 else self.parent_app._path2)
        )[0]

        messagebox.showinfo("Informacion", f"Se exportaran las siguientes subpartes\n{row_idx}\ndel pmdl: {base}", parent=self.master.master)

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
                filetypes=[("TTT SubPart", "*.tttsubpart"), ("Todos los archivos", "*.*")]
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
            dat = bytearray(b'\x00' * 12)
            struct.pack_into("<H", dat, 0, subpart_dat.num_vertices)
            struct.pack_into("<H", dat, 2, subpart_dat.num_bones)
            struct.pack_into("<4B", dat, 4, *subpart_dat.id_bones)
            struct.pack_into("<I", dat, 8, subpart_dat.unk)
            # chunk = dat + chunk

            grosor = self.parent_app._blob if self.path == 0 else self.parent_app._blob2
            grosor = struct.unpack_from("<fff", grosor, 0x40)
            x, y , z = grosor
            chunk = SpartHeader(x, y , z, dat, chunk).build()

            with open(out_path, "wb") as f:
                f.write(chunk)

            messagebox.showinfo("Exportado", f"SubParte {row_idx[0]:02} exportada", parent=self.master.master)
            return

        # ==============================
        # guardar varios archivos
        # ==============================

        out_path = filedialog.askdirectory(
            parent=self.master.master,
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

            dat = bytearray(b'\x00' * 12)
            struct.pack_into("<H", dat, 0, subpart_dat.num_vertices)
            struct.pack_into("<H", dat, 2, subpart_dat.num_bones)
            struct.pack_into("<4B", dat, 4, *subpart_dat.id_bones)
            struct.pack_into("<I", dat, 8, subpart_dat.unk)
            # chunk = dat + chunk

            grosor = self.parent_app._blob if self.path == 0 else self.parent_app._blob2
            grosor = struct.unpack_from("<fff", grosor, 0x40)
            x, y, z = grosor
            chunk = SpartHeader(x, y, z, dat, chunk).build()

            with open(Path(out_path, filename), "wb") as f:
                f.write(chunk)

        messagebox.showinfo("Exportado", f"SubPartes\n{row_idx}\nexportadas", parent=self.master.master)
        # self.parent_app.status_var.set(f"SubParte {row_idx:02} exportada.")

    @error_window_ui
    def _import_subparts(self, chunk=None):
        part_idx = self.master.master._index_opt_left

        row_idx = self.get_selected_row_indices()
        if row_idx is None or len(row_idx) > 1:
            return

        if not chunk:
            path_subpart = filedialog.askopenfilename(
                parent=self.master.master,
                title="Reemplazar Subparte",
                initialdir=".",
                filetypes=[("Archivos SubPart", "*.tttsubpart"),
                           ("Todos los archivos", "*.*")]
            )

            if not path_subpart:
                return

            with open(path_subpart, "rb") as f:
                chunk = f.read()
                chunk =  bytearray(chunk)

            # chunk = chunk[0x10:]
            # chunk = bytearray(chunk)

        # datos de la subparte
        dat_chunk = chunk[0x20:0x2c]
        grosor_2, num_vertices, num_bones, id_bones, unk, chunk = comprobar_header_spart(chunk)

        if len(chunk) == 0:
            raise ValueError("La subpart importada esta vacia")

        # blob de las partes en bytes
        blob = self._get_blob()

        # 1. Verificar estado del toggle de normalización
        normalize_enabled = self.parent_app.normalize_toggle_var.get() if self.parent_app.normalize_toggle_var else True

        if normalize_enabled:

            # 2. Normalizar PMDL principal a grosor máximo si es necesario porque si ya trae valores máximos (0x44) no lo hace
            was_normalized = normalizar_pmdl_completo(
                self.parent_app._blob,
                self.parent_app._hdr.parts_index_offset,
                self.parent_app._parts
            )
            if was_normalized:
                print("✓ PMDL principal normalizado a grosor máximo")
                self._uddate_blobs_ui()

        # 3. Normalizar los vértices de la subparte
        chunk = normalizar_subparte(
            chunk,
            num_vertices,
            num_bones,
            grosor_2
        ) if normalize_enabled else chunk

        part_dat = self._get_subparts()[part_idx][row_idx[0]]
        data_part, cant = import_sub_part(
            blob,
            part_idx,
            part_dat,
            chunk
        )

        # actualizar offset de las subparts
        parts = self._get_subparts()[part_idx]
        for i in range(row_idx[0] + 1, len(parts)):
            parts[i].sub_part_offset+=cant

        # actualizar datos de subpart
        part_dat.num_vertices = num_vertices
        part_dat.num_bones = num_bones
        part_dat.id_bones = list(id_bones)
        part_dat.unk = unk

        # actualizar los parametros en la part
        data_part[(row_idx[0] * 0x10) + 4:(row_idx[0] * 0x10) + 0x10] = dat_chunk

        # obtener el tamaño de la subparte final
        size_part_end = calc_subpart_size(parts[-1].num_vertices, parts[-1].num_bones)

        # quitar los residuos al final de la parte y alinear a 16
        data_part = data_part[:parts[-1].sub_part_offset + size_part_end]
        align_16(data_part)

        # actualizar el blob dict
        blob[f"{part_idx}"] = data_part

        # añadir los cambios al modelo
        replace_part(self.parent_app._blob, self.parent_app._hdr, self.parent_app._parts, data_part, part_idx)

        # ---- Refrescar tabla UI ----
        self.master.master.tab_left.set_table(
            len(self.master.master._sub_parts[part_idx]),
            self.master.master._sub_parts,
            part_idx
        )

        self.select_row(row_idx[0])

        messagebox.showinfo("Importado", f"SubParte importada", parent=self.master.master)

    def import_sub_part_pmdl(self, part_idx:int, row_idx:int, chunk:bytearray, dat_chunk:list):
        """
        reemplaza una subpart existente en el pmdl 1
        :param part_idx: id de la parte
        :param row_idx: id de la subparte
        :param chunk: chunk de vertices
        :param dat_chunk: parametros de la subparte [int, int, list[int], int]
        """

        # blob de las partes en bytes
        blob = self.master.master._blobs
        part_dat = self._get_subparts()[part_idx][row_idx]
        data_part, cant = import_sub_part(
            blob,
            part_idx,
            part_dat,
            chunk
        )
        # actualizar offset de las subparts
        parts = self._get_subparts()[part_idx]
        for i in range(part_idx + 1, len(parts)):
            parts[i].sub_part_offset += cant

        # actualizar valores de la subparte
        # num_vertices, = struct.unpack_from("<H", dat_chunk, 0)
        # num_bones, = struct.unpack_from("<H", dat_chunk, 2)
        # id_bones = list(struct.unpack_from("<4B", dat_chunk, 4))
        # unk, = struct.unpack_from("<I", dat_chunk, 8)

        # actualizar valores de la subparte
        num_vertices = dat_chunk[0]
        num_bones = dat_chunk[1]
        id_bones = dat_chunk[2] # lista de int
        unk = dat_chunk[3]

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

        # seleccionar la subparte en la tabla
        self.select_row(row_idx)

    @error_window_ui
    def _insert_subparts(self):
        part_idx = self.master.master._index_opt_left
        row_idx = self.get_selected_row_indices()

        if not row_idx:
            return
        if len(row_idx) > 1:
            raise ValueError("No se puede insertar si tienes seleccionada mas de una subparte.")

        insert_at = row_idx[0]

        def natural_sort_key(s):
            return [int(t) if t.isdigit() else t.lower()
                    for t in re.split(r'(\d+)', s)]

        paths_subpart = sorted(
            filedialog.askopenfilenames(
                parent=self.master.master,
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

        # 1. Verificar estado del toggle de normalización
        normalize_enabled = self.parent_app.normalize_toggle_var.get() if self.parent_app.normalize_toggle_var else True

        if normalize_enabled:

            # 2. Normalizar PMDL principal a grosor máximo si es necesario porque si ya trae valores máximos (0x44) no lo hace
            was_normalized = normalizar_pmdl_completo(
                self.parent_app._blob,
                self.parent_app._hdr.parts_index_offset,
                self.parent_app._parts
            )
            if was_normalized:
                print("✓ PMDL principal normalizado a grosor máximo")
                self._uddate_blobs_ui()

        for path_subpart in paths_subpart:
            with open(path_subpart, "rb") as f:
                raw = f.read()
                if not raw:
                    raise ValueError(f"El archivo \"{path_subpart}\" esta vacio")

            raw = bytearray(raw)
            # chunk = raw[0x10:]  # ya es bytearray por el slice
            grosor_2, num_vertices, num_bones, id_bones, unk, chunk = comprobar_header_spart(raw)
            dat_chunk = raw[0x20:0x30]

            # 3. Normalizar los vértices de la subparte
            chunk = normalizar_subparte(
                chunk,
                num_vertices,
                num_bones,
                grosor_2
            ) if normalize_enabled else chunk

            # ---- Header de la subparte ----
            # num_vertices, = struct.unpack_from("<H", dat_chunk, 0)
            # num_bones, = struct.unpack_from("<H", dat_chunk, 2)
            # id_bones = list(struct.unpack_from("<4B", dat_chunk, 4))
            # unk, = struct.unpack_from("<I", dat_chunk, 8)

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
                list(id_bones),
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

        self.select_row(row_idx[0]+1)

        # acortar rutas a mostrar
        def last_parts(path, n=2):
            p = Path(path)
            return "/".join(p.parts[-n:])

        short = [last_parts(p, 2) for p in paths_subpart]

        messagebox.showinfo("Insertado", f"SubParte insertada desde la posicion {row_idx[0] + 1:02}\n{short}", parent=self.master.master)

    @error_window_ui
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
        subparts_by_part = self.master.master._sub_parts
        blob = self.master.master._blobs

        # datos del pmdl 2
        blob_2 = self._get_blob()
        subparts_by_part_2 = self._get_subparts()

        if not messagebox.askokcancel(
                "Confirmar Agregar",
                f"Vas a agregar las siguientes subpartes: {row_idx_2}\n\n¿Deseas continuar?",
                parent=self.master.master
        ):
            return

        # Verificar estado del toggle de normalización
        normalize_enabled = self.parent_app.normalize_toggle_var.get() if self.parent_app.normalize_toggle_var else True

        grosor_2 = tuple
        if normalize_enabled:
            # 1. Obtener grosor del PMDL secundario
            grosor_2 = leer_grosor(self.parent_app._blob2)

            # 2. Normalizar PMDL principal a grosor máximo si es necesario porque si ya trae valores máximos (0x44) no lo hace
            was_normalized = normalizar_pmdl_completo(
                self.parent_app._blob,
                self.parent_app._hdr.parts_index_offset,
                self.parent_app._parts
            )
            if was_normalized:
                print("✓ PMDL principal normalizado a grosor máximo")
                self._uddate_blobs_ui()

        for subpart_2 in row_idx_2:
            # Extraer los vertices de la subparte del PMDL secundario
            part_dat_2 = subparts_by_part_2[part_idx_2][subpart_2]
            raw = export_sub_part(
                blob_2,
                part_idx_2,
                part_dat_2
            )
            raw = bytearray(raw)


            # 3. Normalizar los vértices de la subparte
            raw_normalizado = normalizar_subparte(
                raw,
                part_dat_2.num_vertices,
                part_dat_2.num_bones,
                grosor_2
            ) if normalize_enabled else raw

            # data chunk y chunk de la subparte normalizada
            dat_chunk = bytearray(b'\x00' * 0x10)
            struct.pack_into("<H", dat_chunk, 0, part_dat_2.num_vertices)
            struct.pack_into("<H", dat_chunk, 2, part_dat_2.num_bones)
            struct.pack_into("<4B", dat_chunk, 4, *part_dat_2.id_bones)
            struct.pack_into("<I", dat_chunk, 8, part_dat_2.unk)

            chunk = raw_normalizado
            # ---- Header de la subparte ----
            num_vertices = part_dat_2.num_vertices
            num_bones = part_dat_2.num_bones
            id_bones = part_dat_2.id_bones
            unk = part_dat_2.unk

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
            del data_part[
                sub_parts[-1].sub_part_offset + calc_subpart_size(sub_parts[-1].num_vertices, sub_parts[-1].num_bones):]
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

            insert_at += 1

        # ---- Refrescar tabla UI ----
        self.master.master.tab_left.set_table(
            len(self.master.master._sub_parts[part_idx]),
            self.master.master._sub_parts,
            part_idx
        )

        self.master.master.tab_left.select_row(row_idx[0] + 1)

        messagebox.showinfo("Agregada", f"SubParte agregada desde la posicion {row_idx[0] + 1:02}",
                            parent=self.master.master)

    @error_window_ui
    def _delete_subparts(self):
        """
        elimina una subparte en el pmdl 1
        """
        band = False
        part_idx = self.master.master._index_opt_left
        row_idx = self.get_selected_row_indices()
        row_idx_old = copy.deepcopy(row_idx)

        if not messagebox.askokcancel(
                "Confirmar eliminación",
                f"Vas a eliminar las siguientes subpartes: {row_idx}\n\n¿Deseas continuar?",
                parent=self   # ← IMPORTANTE
        ):
            return

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

        messagebox.showinfo("Elimanado", f"SubPartes {row_idx_old} eliminadas correctamente", parent=self.master.master)

    def _uddate_blobs_ui(self):
        blob = self.master.master._blobs
        self.master.master.ids_old = []
        # Actualizar los bytes de las parts desde _blob ya normalizado para que las
        # operaciones de subpartes trabajen con los vértices corregidos
        for i, part in enumerate(self.parent_app._parts):
            off = part.part_offset
            ln = part.part_length
            # reemplazar las id 0xFF
            data_parte = bytearray(self.parent_app._blob[off:off + ln])
            replace_id_ff(parent=self.master.master, part=data_parte)
            blob[str(i)] = bytes(data_parte)

    # =========================
    # PANEL UPDATE
    # =========================
    def _change_labels(self):
        # actualiza el panel central
        row_idx = self._get_selected_row_index()
        if row_idx is None:
            return

        path = self.parent_app._path if self.path == 0 else self.parent_app._path2
        self.path_name = os.path.basename(path) if path else "--"

        ui = self.master.master # clase UiSubparts
        ui.label_name_part.configure(text=f"Pmdl {self.path + 1}: {self.path_name}")
        ui.label_name_subpart.configure(text=f"{t('ui_subparts.subparte')}: {row_idx:02}")
        # ui.tooltip_label_namepart.change_text(path)

        entry = self._get_subparts()[
            ui._index_opt_left if self.path == 0 else ui._index_opt_right
        ][row_idx]

        ui.opt_huesos.set("04")
        ui.on_huesos_changed("04")

        for i, e in enumerate(ui.entry_huesos):
            e.delete(0, "end")
            e.insert(0, f"{entry.id_bones[i]:02X}")

        ui.opt_huesos.set(f"{entry.num_bones:02}")
        ui.on_huesos_changed(f"{entry.num_bones:02}")

        ui.entry_unk.delete(0, "end")
        ui.entry_unk.insert(0, f"{entry.unk:X}")

        # desactivar/activar botones/entry
        ui.btn_save_part.configure(state="normal" if self.path == 0 else "disabled")
        ui.entry_unk.configure(state="normal" if self.path == 0 else "disabled")
        ui.opt_huesos.configure(state="normal" if self.path == 0 else "disabled")
        ui.btn_vertex_ed.configure(state="normal" if self.path == 0 else "disabled")
        ui.btn_mov_up.configure(state="normal" if self.path == 0 else "disabled")
        ui.btn_mov_down.configure(state="normal" if self.path == 0 else "disabled")
        ui.btn_remap.configure(state="normal" if self.path == 0 else "disabled")

class UiSubparts(ctk.CTkToplevel):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.title(APP_TITLE)
        self.geometry("1200x600")
        center_window(self, 1200, 600)
        set_app_icon(self)

        # self.protocol("WM_DELETE_WINDOW", self._disable_close)

        self.grid_columnconfigure((0, 2), weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=220)
        self.grid_rowconfigure(0, weight=1)

        # guarda los parametros de las subpartes, de cada parte del pmdl
        self._sub_parts = []
        self._sub_parts2 = []

        # guarda las id de las subpartes temporalmente
        self.ids_old = []

        # guarda los bytes de las partes del pmdl
        self._blobs = {}
        self._blobs2 = {}

        # indica la id de la parte del pmdl
        self._index_opt_left = 0
        self._index_opt_right = 0

        headers = ["N°", t("ui_subparts.pos"), t("ui_subparts.vert"), t("ui_subparts.n_huesos"), t("ui_subparts.size")]

        # =========================
        # CONTENEDOR IZQUIERDO
        # =========================
        self.left_container = ctk.CTkFrame(self, fg_color="transparent")
        self.left_container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.left_container.grid_rowconfigure(1, weight=1)
        self.left_container.grid_columnconfigure(0, weight=1)

        self.opt_left = ScrollableOptionMenu(
            self.left_container,
            values=[f"{t('ui_subparts.btn_parte')}: 00"],
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
        # self.tooltip_label_namepart = ToolTip(self.label_name_part, "Ruta del archivo .pmdl cargado", timeout=3000)

        self.label_name_subpart = ctk.CTkLabel(
            header,
            text=f"{t('ui_subparts.subparte')}: --",
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
            text=t("ui_subparts.configuracion"),
            font=("Segoe UI", 14, "bold")
        ).grid(row=0, column=0, columnspan=2, pady=(8, 12))

        # N° huesos
        ctk.CTkLabel(
            card_cfg,
            text=t("ui_subparts.n_huesos"),
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
            text=f"{t('ui_subparts.ids')}:",
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
            text=f"{t('ui_subparts.unk')}:",
            font=("Segoe UI", 13)
        ).grid(row=3, column=0, sticky="w", padx=10, pady=10)

        self.entry_unk = ctk.CTkEntry(
            card_cfg,
            placeholder_text="1200C301",
            width=76
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
            text=t("ui_subparts.accion"),
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(8, 12))

        self.btn_save_part = ctk.CTkButton(
            card_actions,
            text=t("ui_subparts.btn_guardar"),
            width=120,
            command=self.on_save_part
        )
        self.btn_save_part.pack(pady=(0, 10))
        # self.btn_save_part_tooltip = ToolTip(self.btn_save_part, "Guarda las modificaciones echas en configuracion")

        self.btn_mov_up = ctk.CTkButton(
            card_actions,
            text=t("ui_subparts.btn_mover_arriba"),
            width=120,
            command=self.mov_up
        )
        self.btn_mov_up.pack(pady=5)

        self.mov_up_st = True

        self.btn_mov_down = ctk.CTkButton(
            card_actions,
            text=t("ui_subparts.btn_mover_abajo"),
            width=120,
            command=self.mov_down
        )
        self.btn_mov_down.pack(pady=(0, 10))

        self.mov_down_st = True

        self.btn_remap = ctk.CTkButton(
            card_actions,
            text=t("ui_subparts.btn_remap_id"),
            width=120,
            command=self.on_options_remap
        )
        self.btn_remap.pack(pady=(0, 10))

        self.btn_vertex_ed = ctk.CTkButton(
            card_actions,
            text=t("ui_subparts.btn_edit_vert"),
            width=120,
            command=self.on_ed_vertex
        )
        self.btn_vertex_ed.pack(pady=(0, 10))

        # =========================
        # CONTENEDOR DERECHO
        # =========================
        self.right_container = ctk.CTkFrame(self, fg_color="transparent")
        self.right_container.grid(row=0, column=2, padx=20, pady=20, sticky="nsew")
        self.right_container.grid_rowconfigure(1, weight=1)
        self.right_container.grid_columnconfigure(0, weight=1)

        self.opt_right = ScrollableOptionMenu(
            self.right_container,
            values=[f"{t('ui_subparts.btn_parte')}: 00"],
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


    def get_data_subpart(self, pmdl=0):
        parts_ids = len(self.master._parts if pmdl == 0 else self.master._parts2)
        if pmdl == 1 and parts_ids == 0:
            self.opt_right.button.configure(state="disabled")
            return

        if parts_ids == 0:
            return

        name_parts = []
        # self._sub_parts = []
        # self._sub_parts2 = []
        self.ids_old = []

        for id_part in range(parts_ids):
            data_part = export_part(self.master._blob if pmdl == 0 else self.master._blob2,
                                    self.master._parts[id_part] if pmdl == 0 else self.master._parts2[id_part])
            # elimina los id 0xff
            data_part = bytearray(data_part)
            replace_id_ff(parent=self, part=data_part)
            # por conveniencia se vuelve a convertir a bytes
            data_part = bytes(data_part)

            if pmdl == 0:
                self._sub_parts.append(parse_subparts_index(data_part))
                self._blobs[f"{id_part}"] = data_part
            else:
                self._sub_parts2.append(parse_subparts_index(data_part))
                self._blobs2[f"{id_part}"] = data_part

            # capa_v = self.master._parts[id_part].part_id if pmdl == 0 else self.master._parts2[id_part].part_id
            name_parts.append(f"{t('ui_subparts.btn_parte')}: {id_part:02}")

        if pmdl == 0:
            self.opt_left.configure(values=name_parts)
            self.opt_left.set(name_parts[0])
            self.tab_left.set_table(len(self._sub_parts[0]), self._sub_parts)
        else:
            self.opt_right.configure(values=name_parts)
            self.opt_right.set(name_parts[0])
            self.tab_right.set_table(len(self._sub_parts2[0]), self._sub_parts2)

        # print(self._sub_parts)

    @error_window_ui
    def on_left_option_changed(self, value):
        # guarda la id de la parte del pmdl 1
        self._index_opt_left = self.opt_left.values.index(value)

        # refresca la UI
        self.tab_left.set_table(
            len(self._sub_parts[self._index_opt_left]),
            self._sub_parts,
            self._index_opt_left
        )

    @error_window_ui
    def on_rigth_option_changed(self, value):
        # guarda la id de la parte del pmdl 2
        self._index_opt_right = self.opt_right.values.index(value)

        # refresca la UI
        self.tab_right.set_table(
            len(self._sub_parts2[self._index_opt_right]),
            self._sub_parts2,
            self._index_opt_right
        )

    def on_huesos_changed(self, value: str):
        unk_vaules = {
            "01" : 0x12004301,
            "02" : 0x1200C301,
            "03" : 0x12014301,
            "04" : 0x1201C301
        }
        # activa los demas entry dependiendo de la cantidad de huesos
        for i in range(4):
            if i < int(value):
                self.entry_huesos[i].configure(state="normal")
            else:
                self.entry_huesos[i].configure(state="disabled")
        self.entry_unk.delete(0, "end")
        self.entry_unk.insert(0, f"{unk_vaules[value]:X}")

    @error_window_ui
    def on_save_part(self):
        part_id = self._index_opt_left
        row_idx = self.tab_left.get_selected_row_indices()

        # validar selección
        if not row_idx:
            return
        if len(row_idx) > 1:
            messagebox.showinfo("Advertencia", "no se puede guardar si tienes mas de una subpart seleccionada", parent=self)
            return

        row = row_idx[0]
        subparts = self._sub_parts[part_id]
        subpart = subparts[row]

        # obtener blob como bytearray (evita conversion doble)
        part_data = bytearray(self._blobs[str(part_id)])

        # ---- leer datos UI ----
        bones_num = int(self.opt_huesos.get())

        # leer ids huesos (más rápido que list comprehension con get repetido)
        id_bones = [0, 0, 0, 0]
        for i in range(4):
            if i < bones_num:
                id_bones[i] = int(self.entry_huesos[i].get(), 16)

        unk_value = int(self.entry_unk.get(), 16)

        # ---- tamaños ----
        num_vertices = subpart.num_vertices
        num_bones_old = subpart.num_bones

        size = calc_subpart_size(num_vertices, num_bones_old)
        size_vertex = calc_subpart_size(num_vertices, num_bones_old, True)

        offset = subpart.sub_part_offset
        dat_subpart = part_data[offset: offset + size]

        # ---- modificar influencias ----
        dat_subpart, cant = bones_strip(dat_subpart, size_vertex, bones_num, subpart)

        part_data[offset: offset + size] = dat_subpart

        # ---- actualizar header subpart ----
        base = (subpart.sub_part * 0x10) + 4
        struct.pack_into("<H", part_data, base + 2, bones_num)
        struct.pack_into("<4B", part_data, base + 4, *id_bones)
        struct.pack_into("<I", part_data, base + 8, unk_value)

        # ---- arreglar offsets siguientes ----
        if cant:
            for i in range(row + 1, len(subparts)):
                sp = subparts[i]
                sp.sub_part_offset += cant
                struct.pack_into("<I", part_data, (i + 1) * 0x10, sp.sub_part_offset)

        # ---- actualizar objeto ----
        subpart.num_bones = bones_num
        subpart.id_bones = id_bones
        subpart.unk = unk_value

        # ---- guardar blob ----
        self._blobs[str(part_id)] = part_data

        # ---- reemplazar en modelo ----
        replace_part(
            self.master._blob,
            self.master._hdr,
            self.master._parts,
            part_data,
            part_id
        )

        # ---- refrescar UI ----
        self.tab_left.set_table(len(subparts), self._sub_parts, part_id)
        self.tab_left.select_row(row)

        messagebox.showinfo("Guardado", "cambios guardados en memoria", parent=self)

    @error_window_ui
    def on_back(self):
        # agregar las id 0xff
        for part_id, blob in self._blobs.items():
            blob = bytearray(blob)
            replace_id_ff(part=blob, reemp=False)

            # ---- Reemplazar parte completa en el modelo ----
            replace_part(
                self.master._blob,
                self.master._hdr,
                self.master._parts,
                blob,
                int(part_id)
            )

        # mostrar la ui pmdl editor
        self.master.on_open_pmdl_editor()
        # Refrescar UI pmdl editor
        self.master.parts_table.populate(self.master._parts)
        self.master.parts_table.update_part_count(self.master._hdr.part_count)

        # destruir esta ui para evitar resetear variables
        self.withdraw()
        self.destroy()

    def _disable_close(self):
        pass  # No hace nada → botón X deshabilitado

    @error_window_ui
    def mov_up(self):
        if not self.mov_up_st:
            return

        self.mov_up_st = False

        part_idx = self._index_opt_left
        table = self.tab_left
        sub_parts = self._sub_parts

        rows = table.get_selected_row_indices()
        if not rows:
            self.mov_up_st = True
            return

        if len(rows) > 1:
            messagebox.showinfo("Informacion", "solo puedes mover una subpart a la vez", parent=self)
            self.mov_up_st = True
            return

        row = rows[0]
        if row == 0:
            self.mov_up_st = True
            return

        # ---- mover data ----
        part_data = move_up(self._blobs, part_idx, sub_parts, row)
        self._blobs[str(part_idx)] = part_data

        # ---- reemplazar en modelo ----
        replace_part(
            self.master._blob,
            self.master._hdr,
            self.master._parts,
            part_data,
            part_idx
        )

        # ---- refrescar UI ----
        table.set_table(len(sub_parts[part_idx]), sub_parts, part_idx)
        table.select_row(row - 1)

        self.mov_up_st = True

    @error_window_ui
    def mov_down(self):
        if not self.mov_down_st:
            return

        self.mov_down_st = False

        part_idx = self._index_opt_left
        table = self.tab_left
        sub_parts = self._sub_parts

        rows = table.get_selected_row_indices()
        if not rows:
            self.mov_down_st = True
            return

        if len(rows) > 1:
            messagebox.showinfo("Informacion", "solo puedes mover una subpart a la vez", parent=self)
            self.mov_down_st = True
            return

        row = rows[0]
        if row + 1 >= len(sub_parts[part_idx]):
            self.mov_down_st = True
            return

        # ---- mover data ----
        part_data = move_up(self._blobs, part_idx, sub_parts, row + 1)
        self._blobs[str(part_idx)] = part_data

        # ---- reemplazar en modelo ----
        replace_part(
            self.master._blob,
            self.master._hdr,
            self.master._parts,
            part_data,
            part_idx
        )

        # ---- refrescar UI ----
        table.set_table(len(sub_parts[part_idx]), sub_parts, part_idx)
        table.select_row(row + 1)

        self.mov_down_st = True

    @error_window_ui
    def on_options_remap(self):
        self.ui_remap =  RemapBones(self)
        part_id = self._index_opt_left

        # obtener las id de los huesos de las diferentes subpartes
        subparts = self._sub_parts[part_id]
        data = []
        for subpart in subparts:
            id_bones = subpart.id_bones[:subpart.num_bones]
            data.append(id_bones)

        self.ui_remap.set_table_values(data)

    def reemplazar_id_bones(self, data: list[int]):
        part_id = self._index_opt_left
        part_bytes = self._blobs[str(part_id)]
        part_bytes = bytearray(part_bytes)

        # reemplazar en subparts
        subparts = self._sub_parts[part_id]
        for i, subpart in enumerate(subparts):
            subparts[i].id_bones = copy.deepcopy((data[i] + [0] * 4)[:4])

            # reemplazar en part en blobs
            struct.pack_into("<4B", part_bytes, (0x10*i) + 8, *subparts[i].id_bones)

        self._blobs[str(part_id)] = part_bytes

        # ---- reemplazar en modelo ----
        replace_part(
            self.master._blob,
            self.master._hdr,
            self.master._parts,
            part_bytes,
            part_id
        )
        table = self.tab_left

        # ---- refrescar UI ----
        table.set_table(len(self._sub_parts[part_id]), self._sub_parts, part_id)
        table.select_row(0)

        messagebox.showinfo("Informacion", f"Las id fueron reemplazadas en la Parte: {part_id:02}", parent=self)


    @error_window_ui
    def on_ed_vertex(self):
        part_id = self._index_opt_left
        row_idx = self.tab_left.get_selected_row_indices()
        if len(row_idx) > 1:
            messagebox.showinfo("Advertencia",
                                "Tienes mas de una subpart seleccionada", parent=self)
            return

        if not row_idx:
            return

        # datos de la subpart
        subpart = self._sub_parts[part_id][row_idx[0]]
        grosor = leer_grosor(self.master._blob)
        id_bones = subpart.id_bones[:subpart.num_bones]
        unk = subpart.unk

        part_data = self._blobs.get(f"{part_id}", None)
        part_data = bytearray(part_data)

        size = calc_subpart_size(subpart.num_vertices, subpart.num_bones)
        size_vertex = calc_subpart_size(subpart.num_vertices, subpart.num_bones, True)
        subpart_data = part_data[subpart.sub_part_offset: subpart.sub_part_offset + size]
        # pasa los vertices de la subpart a una lista
        list_vertices = split_fixed(subpart_data, size_vertex)

        # formatear datos
        vertices = []
        for vertex in list_vertices:
            dat = {}

            pos_x, = struct.unpack_from("<h", vertex, (subpart.num_bones * 2) + 2)
            pos_y, = struct.unpack_from("<h", vertex, (subpart.num_bones * 2) + 4)
            pos_z, = struct.unpack_from("<h", vertex, (subpart.num_bones * 2) + 6)

            dat["pos"] = [pos_x, pos_y, pos_z]

            uv, = struct.unpack_from("<B", vertex, subpart.num_bones * 2)
            uv_1, = struct.unpack_from("<B", vertex, (subpart.num_bones * 2) + 1)

            dat["uv"] = [uv, uv_1]

            bones = []
            for i in range(subpart.num_bones):
                bone, = struct.unpack_from(">H", vertex, i * 2)
                bones.append(bone)

            dat["weights"] = bones

            vertices.append(dat)

        data_subpart = {
            'grosor': grosor,
            'id_bones': id_bones,
            'unk': unk,
            'vertices': vertices
        }

        path = self.tab_left.parent_app._path
        name_pmdl = os.path.basename(path)
        path = self.master.tooltip_path2_entry._user_hide(path)
        self.editor = VertexEditor(self, data_subpart, f"{row_idx[0]:02}", name_pmdl, path)