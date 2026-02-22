import json
import struct
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.logic_sub_parts_pmdl.operations import calc_subpart_size
from app.utils.ui_error_window import error_window_ui

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class VertexEditor(ctk.CTkToplevel):
    def __init__(self, parent, data_subpart:dict, idsubpart:str, namepmdl:str, path:str, **kwargs):
        super().__init__(parent)
        self.escala = 0.00051875

        self.title(f"Pmdl Editor - Subpart N°: ** {idsubpart} ** - {namepmdl}")
        self.geometry("920x520")
        self.attributes("-toolwindow", True)
        self.resizable(False, False)
        # self.protocol("WM_DELETE_WINDOW", lambda: None)

        # ----- MODAL -----
        self.transient(parent)  # siempre encima del padre
        self.grab_set()  # bloquea interacción con otras ventanas
        self.focus()  # recibe el foco

        # opcional: centrar respecto al padre
        self.after(10, lambda: self.center(parent))

        self.vertices = None
        self.entries = []

        # ----- HEADER FUERA DEL SCROLL -----
        self.header = ctk.CTkFrame(self)
        self.header.pack(fill="x", padx=10, pady=(10,0))

        self.create_header(self.header)

        # ----- SCROLL SOLO PARA LAS FILAS -----
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Frame interno de filas
        self.table = ctk.CTkFrame(self.scroll)
        self.table.pack(anchor="nw")

        self.grosor = data_subpart['grosor']
        self._procesar_vertices(data_subpart['vertices'])
        self.load_vertices(data_subpart['vertices'])

        # ----- FRAME DE BOTONES -----
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.pack(pady=5)

        ctk.CTkButton(
            self.btn_frame,
            text="Export datos",
            width=120,
            command=self.on_export_data
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.btn_frame,
            text="Importar datos",
            width=120,
            command=self.on_import_data
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.btn_frame,
            text="Guardar cambios",
            width=140,
            command=self.on_save_change
        ).pack(side="left", padx=5)

        # ----- FRAME DEL PATH (debajo de botones) -----
        self.path_frame = ctk.CTkFrame(self)
        self.path_frame.pack(fill="x", padx=10, pady=(0,8))

        self.path_label = ctk.CTkLabel(
            self.path_frame,
            text=f"Ruta: {path}",
            anchor="w",   # texto alineado a la izquierda dentro del label
        )
        self.path_label.pack(side="left", fill="x", expand=True)


    # ----------------------------
    def create_header(self, parent):
        headers = [
            "ID",
            "X", "Y", "Z",
            "U", "V",
            "Peso 1", "Peso 2", "Peso 3", "Peso 4"
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

        # ---- LIMPIAR TABLA ----
        for widget in self.table.winfo_children():
            widget.destroy()

        # ---- LIMPIAR LISTAS ----
        self.entries.clear()
        self.vertices = vertices

        # ---- CREAR FILAS NUEVAS ----
        for r, v in enumerate(self.vertices):

            row_entries = []

            # ---- ID (solo lectura) ----
            id_entry = ctk.CTkEntry(self.table, width=80, justify="center")
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
                e = ctk.CTkEntry(self.table, width=80, justify="center")
                e.insert(0, str(value))
                e.grid(row=r, column=c + 1, padx=2, pady=2)
                row_entries.append(e)

            # ---- Pesos ----
            for i in range(4):
                e = ctk.CTkEntry(self.table, width=85, justify="center")

                if i < weight_count:
                    e.insert(0, str(weights[i]))
                else:
                    e.insert(0, "")
                    e.configure(state="disabled")

                e.grid(row=r, column=6 + i, padx=2, pady=2)
                row_entries.append(e)

            self.entries.append(row_entries)

    # ----------------------------
    def on_save_change(self):
        result = []

        for row in self.entries:
            try:
                # row[0] es ID, se ignora
                x, y, z = float(row[1].get()), float(row[2].get()), float(row[3].get())
                u, v = float(row[4].get()), float(row[5].get())

                weights = []
                for w in row[6:10]:
                    if w.cget("state") == "normal":
                        val = w.get().strip()
                        if val:
                            weights.append(float(val))

                result.append({
                    "pos": (x, y, z),
                    "uv": (u, v),
                    "weights": weights
                })

            except ValueError:
                raise ValueError("Error en fila")

        # print("Vertices editados:")
        # for v in result:
        #     print(v)

        # formatear la lista a bytes
        out = bytearray()

        for v in result:

            # ---- weights  (<H)
            # si vienen como float 0..1 los conviertes a entero 0..65535
            for w in v["weights"]:
                w_int = int(w)
                out += struct.pack("<H", w_int)

            # ---- uv (<B)
            # conviertes float 0..1 a 0..255
            for uv in v["uv"]:
                uv_int = int(uv)
                out += struct.pack("<B", uv_int)

            # ---- pos (<H)
            for p in v["pos"]:
                p_int = int(p)
                out += struct.pack("<H", p_int)


        # obtener la id de la parte y la id de la subparte
        part_id = self.master._index_opt_left
        row_idx = self.master.tab_left.get_selected_row_indices()[0]

        # datos de la subparte y tamaño del vertex
        subpart = self.master._sub_parts[part_id][row_idx]
        size_vertex = calc_subpart_size(subpart.num_vertices, subpart.num_bones, True)

        dat_chunk = []
        dat_chunk.append(len(out)//size_vertex)
        dat_chunk.append(subpart.num_bones)
        dat_chunk.append(subpart.id_bones)
        dat_chunk.append(subpart.unk)

        # actualizar la subpart en el pmdl
        self.master.tab_left.import_sub_part_pmdl(part_id, row_idx, out, dat_chunk)

        messagebox.showinfo("Guardado", "Se guardaron los datos", parent=self)

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
                            weights.append(float(val))

                result.append({
                    "id_v": id_v,
                    "pos": (x, y, z),
                    "uv": (u, v),
                    "weights": weights
                })

            except ValueError:
                raise "Error en fila"

        # convertir tuplas a listas
        for v in result:
            v["pos"] = list(v["pos"])
            v["uv"] = list(v["uv"])

        ruta = filedialog.asksaveasfilename(
            title="Guardar datos de los vertices",
            defaultextension=".json",
            filetypes=[("Archivos de json", "*.json"), ("Todos", "*.*")]
        )
        if not ruta:
            return

        data = {
            "grosor": list(self.grosor),
            "vertices": result
        }

        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        messagebox.showinfo("Guardado", "Se guardaron los datos", parent=self)

    def on_import_data(self):

        ruta = filedialog.askopenfilename(
            title="Seleccionar JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")]
        )

        if not ruta:
            return

        with open(ruta, "r", encoding="utf-8") as f:
            data = json.load(f)

        for v in data:
            v["pos"] = tuple(v["pos"])
            v["uv"] = tuple(v["uv"])

        self.load_vertices(data)
        messagebox.showinfo("Cargado", "Datos cargados", parent=self)

    def _procesar_vertices(self, vertices:list):
        GROSOR_MAXIMO = 68.0

        grosor_x = self.grosor[0] if self.grosor[0] > 0 else GROSOR_MAXIMO
        grosor_y = self.grosor[1] if self.grosor[1] > 0 else GROSOR_MAXIMO
        grosor_z = self.grosor[2] if self.grosor[2] > 0 else GROSOR_MAXIMO

        factor_x = grosor_x / GROSOR_MAXIMO
        factor_y = grosor_y / GROSOR_MAXIMO
        factor_z = grosor_z / GROSOR_MAXIMO

        for v in vertices:
            x = v['pos'][0] * self.escala * factor_x * -1
            y = v['pos'][1] * self.escala * factor_y * -1
            z = v['pos'][2] * self.escala * factor_z

            v['pos'] = (x, y, z)


