import copy
import json
import struct
import customtkinter as ctk
from tkinter import filedialog, messagebox, Toplevel
from app.logic_sub_parts_pmdl.header_subpart import SpartHeader
from app.logic_sub_parts_pmdl.operations import calc_subpart_size
from app.logic_sub_parts_pmdl.quant16_converter import game16_to_float, float_to_game16, procesar_vertices, \
    procesar_pesos, ESCALA
from app.utils.icon import set_app_icon
from app.utils.lang import t
from app.utils.ui_error_window import error_window_ui
from app.utils.window import center_to_window


def weight_color(value):
    if value == "N/A":
        return "#1f1f1f"

    v = float(value)

    if v <= 0.25:  # azul → cian
        t = v / 0.25
        r = 0
        g = int(255 * t)
        b = 255

    elif v <= 0.5:  # cian → verde
        t = (v - 0.25) / 0.25
        r = 0
        g = 255
        b = int(255 * (1 - t))

    elif v <= 0.75:  # verde → amarillo
        t = (v - 0.5) / 0.25
        r = int(255 * t)
        g = 255
        b = 0

    else:  # amarillo → rojo
        t = (v - 0.75) / 0.25
        r = 255
        g = int(255 * (1 - t))
        b = 0

    # 🔧 reducir brillo (tipo Blender UI)
    factor = 0.35
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)

    return f"#{r:02x}{g:02x}{b:02x}"

WEIGHT_VALUES = ["N/A"] + [f"{i / 10:.1f}" for i in range(11)]
WEIGHT_TEXT = [
    t('ui_edit_vert.col_peso_1'),
    t('ui_edit_vert.col_peso_2'),
    t('ui_edit_vert.col_peso_3'),
    t('ui_edit_vert.col_peso_4')
]

class VertexEditor(ctk.CTkToplevel):
    def __init__(self, parent, data_subpart:dict, idsubpart:str, namepmdl:str, path:str, **kwargs):
        super().__init__(parent)
        self.escala = ESCALA
        self.duplicate_map = {}
        self.rows_vertex = []
        #almacena valor del peso en ui normalizador
        self.val_pes = None

        self.title(f"{t('ui_edit_vert.titulo')} ** {idsubpart} ** - {namepmdl}")
        self.geometry("920x520")
        self.attributes("-toolwindow", True)
        self.resizable(False, False)
        # self.protocol("WM_DELETE_WINDOW", lambda: None)

        # ----- MODAL -----
        self.transient(parent)  # siempre encima del padre
        self.grab_set()  # bloquea interacción con otras ventanas
        self.focus()  # recibe el foco

        set_app_icon(self)
        # opcional: centrar respecto al padre
        self.after(20, lambda: self.center(parent))

        self.vertices = None
        self.entries = []

        # ----- BOTÓN SUPERIOR (antes del header) -----
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(
            self.top_frame,
            text=t("ui_edit_vert.btn_edit_pesos"),
            width=190,
            command=self.open_dual_panel_window
        ).pack(side="left", pady=10)

        # ----- HEADER FUERA DEL SCROLL -----
        self.header = ctk.CTkFrame(self)
        self.header.pack(fill="x", padx=10, pady=(0, 0))

        self.create_header(self.header)

        # ----- SCROLL SOLO PARA LAS FILAS -----
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Frame interno de filas
        self.table = ctk.CTkFrame(self.scroll)
        self.table.pack(anchor="nw")

        self.grosor = data_subpart['grosor']
        self.id_bones = data_subpart['id_bones']
        self.unk = data_subpart['unk']
        procesar_vertices(self.grosor, self.escala, data_subpart['vertices'])
        procesar_pesos(data_subpart['vertices'])
        self.load_vertices(data_subpart['vertices'])

        # ----- FRAME DE BOTONES -----
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.pack(pady=5)

        ctk.CTkButton(
            self.btn_frame,
            text=t("ui_edit_vert.btn_exportar"),
            width=120,
            command=self.on_export_data
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.btn_frame,
            text=t("ui_edit_vert.btn_importar"),
            width=120,
            command=self.on_import_data
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.btn_frame,
            text=t("ui_edit_vert.btn_save"),
            width=140,
            command=self.on_save_change
        ).pack(side="left", padx=5)

        # ----- FRAME DEL PATH (debajo de botones) -----
        self.path_frame = ctk.CTkFrame(self)
        self.path_frame.pack(fill="x", padx=10, pady=(0,8))

        self.path_label = ctk.CTkLabel(
            self.path_frame,
            text=f"{t('ui_edit_vert.ruta')}: {path}",
            anchor="w",
        )
        self.path_label.pack(side="left", fill="x", expand=True)

        if self.grosor != (512.0, 512.0, 512.0):
            messagebox.showinfo(t("ui_edit_vert.t_warning"), t("ui_edit_vert.mesg_pmdl_normalizar"), parent=self)
            return


    # ----------------------------
    def create_header(self, parent):
        headers = [
            "ID",
            "X", "Y", "Z",
            "UV X", "UV Y",
            t('ui_edit_vert.col_peso_1'), t('ui_edit_vert.col_peso_2'), t('ui_edit_vert.col_peso_3'), t('ui_edit_vert.col_peso_4')
        ]

        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(
                parent,
                text=text,
                width=80,
                fg_color="#2b2b2b",
                corner_radius=6
            )
            lbl.grid(row=0, column=col, padx=3, pady=5)

    # ----------------------------
    def load_vertices(self, vertices: list):
        def update_weight_color(widget, value, row_idx=None, weight_idx=None):
            color = weight_color(value)

            widget.configure(
                fg_color=color,
                button_color=color,
                button_hover_color=color
            )

            # sincronizar duplicados
            if row_idx is not None and weight_idx is not None:
                for idx in self.duplicate_map.get(row_idx, []):
                    if idx == row_idx:
                        continue

                    target_widget = self.entries[idx][6 + weight_idx]

                    if target_widget.cget("state") == "normal":
                        target_widget.set(value)

                        # aplicar color también
                        c = weight_color(value)
                        target_widget.configure(
                            fg_color=c,
                            button_color=c,
                            button_hover_color=c
                        )

        # ---- LIMPIAR TABLA ----
        for widget in self.table.winfo_children():
            widget.destroy()

        # ---- LIMPIAR LISTAS ----
        self.entries.clear()
        self.vertices = vertices
        self.rows_vertex = []

        # Mapa: fila -> [filas duplicadas]
        self.duplicate_map = {}

        key_map = {}

        for idx, v in enumerate(vertices):
            key = (
                v["pos"][0],
                v["pos"][1],
                v["pos"][2],
                v["uv"][0],
                v["uv"][1]
            )

            key_map.setdefault(key, []).append(idx)

        # construir acceso directo
        for indices in key_map.values():
            for idx in indices:
                self.duplicate_map[idx] = indices

        # ---- CREAR FILAS NUEVAS ----
        for r, v in enumerate(self.vertices):
            row_color = "#2b2b2b" if r % 2 else "#333333"

            row_entries = []

            # ---- ID (solo lectura) ----
            id_entry = ctk.CTkEntry(
                self.table,
                width=80,
                justify="center",
                fg_color=row_color
            )
            id_entry.insert(0, str(r))
            id_entry.configure(state="disabled")
            id_entry.grid(row=r, column=0, padx=2, pady=2)
            row_entries.append(id_entry)

            # ---- Datos base ----
            base_data = [
                v["pos"][0], v["pos"][1], v["pos"][2],
                v["uv"][0], v["uv"][1],
            ]

            weights = v.get("weights", [])
            weight_count = len(weights)

            # ---- XYZ + UV ----
            for c, value in enumerate(base_data):
                e = ctk.CTkEntry(
                    self.table,
                    width=80,
                    justify="center",
                    fg_color=row_color
                )
                e.insert(0, str(value))
                e.grid(row=r, column=c + 1, padx=2, pady=2)
                row_entries.append(e)

            # ---- Pesos ----
            for i in range(4):

                w = ctk.CTkOptionMenu(
                    self.table,
                    values=WEIGHT_VALUES,
                    width=85,
                    command=lambda v, widget=None: update_weight_color(widget, v)
                )

                # fix lambda referencia
                def make_callback(row_idx, weight_idx, widget):
                    return lambda value: update_weight_color(widget, value, row_idx, weight_idx)

                w.configure(command=make_callback(r, i, w))

                if i < weight_count:
                    value = weights[i]

                    if value == "N/A":
                        w.set("N/A")
                    else:
                        w.set(f"{float(value):.1f}")
                else:
                    w.set("N/A")
                    w.configure(state="disabled")

                # aplicar color inicial
                update_weight_color(w, w.get())

                w.grid(row=r, column=6 + i, padx=2, pady=2)
                row_entries.append(w)

            self.entries.append(row_entries)
            self.rows_vertex.append(row_entries)

    # ----------------------------
    @error_window_ui
    def on_save_change(self):
        if self.grosor != (512.0, 512.0, 512.0):
            messagebox.showinfo(t("ui_edit_vert.t_warning"), t("ui_edit_vert.mesg_pmdl_normalizar"), parent=self)
            return

        result = []

        for row in self.entries:
            try:
                # row[0] es ID, se ignora
                x, y, z = float(row[1].get()), float(row[2].get()), float(row[3].get())
                u, v = int(row[4].get()), int(row[5].get())
                if not (0 <= u <= 255 and 0 <= v <= 255):
                    raise ValueError(t("ui_edit_vert.error_uv"))

                weights = []
                for w in row[6:10]:
                    if w.cget("state") == "normal":
                        val = w.get().strip()
                        if val:
                            weights.append(float(val) if val.lower() != "n/a" else "N/A")
                        else:
                            weights.append(0)

                if all(x == "N/A" for x in weights):
                    raise ValueError(t("ui_edit_vert.error_na"))

                result.append({
                    "pos": [x, y, z],
                    "uv": [u, v],
                    "weights": copy.deepcopy(weights)
                })

            except Exception:
                raise ValueError(t("ui_edit_vert.error_fila"))

        # print("Vertices editados:")
        # for v in result:
        #     print(v)

        # formatear la lista a bytes
        out = bytearray()
        data = {
            'vertices': result
        }
        procesar_vertices(self.grosor, self.escala, data['vertices'], False)
        procesar_pesos(data['vertices'], False)

        for v in result:

            # ---- weights  (>H)
            for w in v["weights"]:
                out += struct.pack(">H", w)

            # ---- uv (<B)
            for uv in v["uv"]:
                out += struct.pack("<B", uv)

            # ---- pos (<h)
            for p in v["pos"]:
                out += struct.pack("<h", p)



        # obtener la id de la parte y la id de la subparte
        # part_id = self.master._index_opt_left
        # row_idx = self.master.tab_left.get_selected_row_indices()[0]

        # datos de la subparte y tamaño del vertex
        # subpart = self.master._sub_parts[part_id][row_idx]
        # size_vertex = calc_subpart_size(subpart.num_vertices, subpart.num_bones, True)
        size_vertex = 8 + (len(self.id_bones)*2)

        # dat_chunk = []
        # dat_chunk.append() # num vertices
        # dat_chunk.append() # num de bones
        # self.id_bones[:] = (self.id_bones + [0, 0, 0, 0])[:4]
        # dat_chunk.append(self.id_bones)
        # dat_chunk.append(self.unk)

        dat = bytearray(b'\x00' * 12)
        struct.pack_into("<H", dat, 0, len(out)//size_vertex)
        struct.pack_into("<H", dat, 2, len(self.id_bones))
        struct.pack_into("<4B", dat, 4, *(self.id_bones + [0, 0, 0, 0])[:4])
        struct.pack_into("<I", dat, 8, self.unk)

        # usar el metodo import subpart con header para evitar cualquier inconveniente
        chunk = SpartHeader(self.grosor[0], self.grosor[1], self.grosor[2], dat, out).build()

        # actualizar la subpart en el pmdl
        # self.master.tab_left.import_sub_part_pmdl(part_id, row_idx, out, dat_chunk)

        self.master.tab_left._import_subparts(chunk=chunk)

        # messagebox.showinfo(t("ui_edit_vert.t_correcto"), t("ui_edit_vert.msg_guardado"), parent=self)

    def center(self, parent):
        self.update_idletasks()

        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()

        w = self.winfo_width()
        h = self.winfo_height()

        x = px + (pw // 2 - w // 2)
        y = py + (ph // 2 - h // 2)

        self.geometry(f"+{x}+{y}")

    def on_back_window(self):
        self.grab_release()
        self.destroy()

    @error_window_ui
    def on_export_data(self):
        result = []

        for row in self.entries:
            try:
                id_v = row[0].get()
                x, y, z = float(row[1].get()), float(row[2].get()), float(row[3].get())
                u, v = int(row[4].get()), int(row[5].get())

                weights = []
                for w in row[6:10]:
                    if w.cget("state") == "normal":
                        val = w.get().strip()
                        if val:
                            weights.append("N/A" if not val or str(val).lower() == "n/a" else float(val))

                result.append({
                    "id_v": id_v,
                    "pos": [x, y, z],
                    "uv": [u, v],
                    "weights": weights
                })

            except ValueError:
                raise ValueError(t("ui_edit_vert.error_fila"))

        # # convertir tuplas a listas
        # for v in result:
        #     v["pos"] = list(v["pos"])
        #     v["uv"] = list(v["uv"])

        ruta = filedialog.asksaveasfilename(
            parent=self,
            title=t("ui_edit_vert.dlg_export"),
            defaultextension=".json",
            filetypes=[(t("port_ttt.file_json"), "*.json"), (t("port_ttt.all_files"), "*.*")]
        )
        if not ruta:
            return

        data = {
            "type": "subpart",
            "grosor": list(self.grosor),
            "id_bones":  [f"0x{n:02X}" for n in self.id_bones],
            "unk": self.unk,
            "vertices": result
        }

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        messagebox.showinfo(t("ui_edit_vert.t_correcto"), t("ui_edit_vert.msg_guardado"), parent=self)

    @error_window_ui
    def on_import_data(self):
        if self.grosor != (512.0, 512.0, 512.0):
            messagebox.showinfo(t("ui_edit_vert.t_warning"), t("ui_edit_vert.mesg_pmdl_normalizar"), parent=self)
            return

        ruta = filedialog.askopenfilename(
            parent=self,
            title=t("ui_edit_vert.dlg_json"),
            filetypes=[(t("port_ttt.file_json"), "*.json"), (t("port_ttt.all_files"), "*.*")]
        )

        if not ruta:
            return

        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data["type"].strip().lower() != "subpart":
            raise ValueError(t("ui_edit_vert.error_json"))

        if tuple(data["grosor"]) != (512.0, 512.0, 512.0):
            messagebox.showinfo(t("ui_edit_vert.t_warning"), t("ui_edit_vert.erro_subpart_normalizada"), parent=self)
            return

        # asegurar usar un decimal
        for v in data["vertices"]:
            v["weights"] = [
                "N/A" if str(w).lower() == "n/a" else round(float(w), 1)
                for w in v.get("weights", [])
            ]

        self.load_vertices(data["vertices"])

        self.grosor = tuple(data["grosor"])
        self.id_bones = [int(x, 16) for x in data["id_bones"]]
        self.unk = data["unk"]

        messagebox.showinfo(t("ui_edit_vert.t_correcto"), t("ui_edit_vert.msg_dt_load"), parent=self)

    def open_dual_panel_window(self):

        win = ctk.CTkToplevel(self)
        win.title(t("ui_edit_vert.btn_edit_pesos"))
        win.geometry("350x150")
        win.resizable(False, False)

        # opcional: comportamiento modal
        win.transient(self)
        win.grab_set()
        win.focus()

        # ----- FRAME PRINCIPAL -----
        main_frame = ctk.CTkFrame(win)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # =========================
        # 🔹 IZQUIERDA
        # =========================
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.pack(side="left", anchor="w")

        opt_left = ctk.CTkOptionMenu(
            left_frame,
            values=WEIGHT_VALUES,
            width=70
        )
        opt_left.pack(anchor="center", pady=5)

        def apply_color(value):
            c = weight_color(value)
            opt_left.configure(
                fg_color=c,
                button_color=c,
                button_hover_color=c
            )

        apply_color(opt_left.get())
        opt_left.configure(command=apply_color)


        btn_left = ctk.CTkButton(
            left_frame,
            text=t("ui_edit_vert.btn_apli_pesos"),
            width=100,
            command=lambda: self.asignar_pesos(opt_left.get())
        )
        btn_left.pack(anchor="center", pady=5)


        btn_left_1 = ctk.CTkButton(
            left_frame,
            text=t("ui_edit_vert.btn_apli_pesos_col"),
            width=100,
            command=lambda: self.asignar_pesos(opt_left.get(), 4 - WEIGHT_TEXT.index(self.val_pes))
        )
        btn_left_1.pack(anchor="center", pady=5, padx=5)

        # =========================
        # 🔹 DERECHA
        # =========================
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", anchor="e")

        # contenedor para centrar
        center_container = ctk.CTkFrame(right_frame, fg_color="transparent")
        center_container.pack(expand=True)

        opt_right = ctk.CTkOptionMenu(
            center_container,
            values=WEIGHT_TEXT,
            width=100,
            command=self.set_val_pes
        )
        opt_right.pack(pady=10)
        opt_right._command(WEIGHT_TEXT[0])

        # botones inferiores juntos
        btns_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        btns_frame.pack()

        btn_ok = ctk.CTkButton(
            btns_frame,
            text=t("ui_edit_vert.btn_left"),
            width=80,
            command=lambda: self.mover_pesos(4 - WEIGHT_TEXT.index(self.val_pes), 1, opt_right)
        )
        btn_ok.pack(side="left", padx=5, pady=5)

        btn_cancel = ctk.CTkButton(
            btns_frame,
            text=t("ui_edit_vert.btn_rigth"),
            width=80,
            command=lambda: self.mover_pesos(4 - WEIGHT_TEXT.index(self.val_pes), -1, opt_right)
        )
        btn_cancel.pack(side="left", padx=5, pady=5)

        # opcional: centrar respecto al parent
        center_to_window(win, self)

        return win

    def set_val_pes(self, value):
        self.val_pes = value

    def asignar_pesos(self, value, colw=None):
        for row in self.rows_vertex:
            for col in range(1, 5):

                # aplicar a una sola columna si colw no es None
                if colw is not None and col != colw:
                    continue

                widget = row[-col]

                if widget.cget("state") == "normal":
                    widget.set(value)
                    widget._command(value)

    def mover_pesos(self, colw:int, direc:int, option):
        res = colw+direc
        print(res)
        if res > 4 or res < 1:
            return

        for row in self.rows_vertex:
            widget = row[-colw]

            if widget.cget("state") == "disabled":
                return

            widget_2 = row[-(res)]
            if widget_2.cget("state") == "disabled":
                return

            value = widget.get()
            if value == "N/A":
                continue
            # widget._command("N/A")

            widget_2.set(value)
            widget_2._command(value)
            # widget.set("N/A")

        # cambiar color en columna anterior
        for row in self.rows_vertex:
            widget = row[-colw]
            widget.set("N/A")
            widget._command("N/A")

        # cambiar option weight
        option.set(WEIGHT_TEXT[-(res)])
        option._command(WEIGHT_TEXT[-(res)])
