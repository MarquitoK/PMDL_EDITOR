import customtkinter as ctk

from app.utils.icon import set_app_icon
from app.utils.lang import t
from app.utils.ui_error_window import error_window_ui
from app.utils.window import center_to_window

GRID_FONT = ("Consolas", 15)
class RemapBones(ctk.CTkToplevel):

    def __init__(self, master=None):
        super().__init__(master)

        self.title("Remap ID(HEX)")  # título técnico, no se traduce
        self.geometry("595x360")
        self.resizable(False, False)
        set_app_icon(self)

        center_to_window(self, self.master)

        # ----- MODAL -----
        self.transient(self.master)  # siempre encima del padre
        self.grab_set()  # bloquea interacción con otras ventanas
        self.focus()  # recibe el foco

        self.selected_row = None
        self.rows = []
        self.color_normal = ctk.ThemeManager.theme["CTkEntry"]["fg_color"]
        self.color_alt = "#2E2E2E"
        self.color_selected = "#1F538D"

        # =============================
        # FRAME IZQUIERDO (TABLA)
        # =============================

        self.frame_left = ctk.CTkFrame(self)
        self.frame_left.pack(side="left", fill="both", expand=True, padx=(10,5), pady=10)

        headers = ["N°", "1", "2", "3", "4"]

        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(
                self.frame_left,
                text=text,
                width=61,
                anchor="center",
                font=ctk.CTkFont(weight="bold")
            )
            lbl.grid(row=0, column=col, padx=0.5, pady=(0,4))

        self.table = ctk.CTkScrollableFrame(self.frame_left)
        self.table.grid(row=1, column=0, columnspan=5, sticky="nsew")

        self.frame_left.grid_rowconfigure(1, weight=1)

        # =============================
        # CONTENEDOR DERECHO
        # =============================

        self.frame_right_container = ctk.CTkFrame(self)
        self.frame_right_container.pack(side="right", fill="y", padx=(5,10), pady=10)

        # =============================
        # FRAME DERECHO (CONTROLES)
        # =============================

        self.frame_right = ctk.CTkFrame(self.frame_right_container)
        self.frame_right.pack(fill="x")

        self.label_a = ctk.CTkLabel(self.frame_right, text="ID 1")
        self.label_a.grid(row=0, column=0, padx=5, pady=(10,5))

        self.label_b = ctk.CTkLabel(self.frame_right, text="ID 2")
        self.label_b.grid(row=0, column=1, padx=5, pady=(10,5))

        self.entry_a = ctk.CTkEntry(self.frame_right, width=70, justify="center",
            font=GRID_FONT)
        self.entry_a.grid(row=1, column=0, padx=5, pady=(0,10))

        self.entry_b = ctk.CTkEntry(self.frame_right, width=70, justify="center",
            font=GRID_FONT)
        self.entry_b.grid(row=1, column=1, padx=5, pady=(0,10))

        self.btn_add = ctk.CTkButton(self.frame_right, text=t("ui_remap_id.btn_1"), command=self.buscar_reemplazar)
        self.btn_add.grid(row=2, column=0, columnspan=2, pady=5, padx=10, sticky="ew")

        self.btn_update = ctk.CTkButton(self.frame_right, text=t("ui_remap_id.btn_2"), command=self.reemplazar_todo)
        self.btn_update.grid(row=3, column=0, columnspan=2, pady=5, padx=10, sticky="ew")

        self.btn_delete = ctk.CTkButton(self.frame_right, text=t("ui_remap_id.btn_3"), command=self.reemplazar_columna)
        self.btn_delete.grid(row=4, column=0, columnspan=2, pady=5, padx=10, sticky="ew")

        self.frame_right.grid_columnconfigure((0,1), weight=1)

        # =============================
        # FRAME INFERIOR (BOTÓN EXTRA)
        # =============================

        self.frame_bottom = ctk.CTkFrame(self.frame_right_container)
        self.frame_bottom.pack(fill="x", pady=(10,0))

        self.btn_apply = ctk.CTkButton(
            self.frame_bottom,
            text=t("ui_remap_id.save"),
            command=self.aplicar_cambios
        )
        self.btn_apply.pack(fill="x", padx=10, pady=10)

    # ==================================
    # OPERACIONES
    # ==================================
    @error_window_ui
    def reemplazar_todo(self):
        id_1 = self.entry_a.get().strip()
        if not id_1:
            return
        id_1 = int(id_1, 16)
        if not (0 <= id_1 <= 0xFF):
            raise ValueError(t("ui_remap_id.error_id1"))

        data = self.get_table_values()

        for i, fil in enumerate(data):
            for j, col in enumerate(fil):
                data[i][j] = id_1

        self.set_table_values(data)

    @error_window_ui
    def buscar_reemplazar(self):

        id_1 = self.entry_a.get().strip()
        id_2 = self.entry_b.get().strip()

        if not id_1 or not id_2:
            return

        id_1 = int(id_1, 16)
        id_2 = int(id_2, 16)

        if not (0 <= id_1 <= 0xFF):
            raise ValueError(t("ui_remap_id.error_id1"))

        if not (0 <= id_2 <= 0xFF):
            raise ValueError(t("ui_remap_id.error_id1"))

        data = self.get_table_values()

        for i, fil in enumerate(data):
            for j, col in enumerate(fil):
                if col == id_1:
                    data[i][j] = id_2

        self.set_table_values(data)

    @error_window_ui
    def reemplazar_columna(self):

        id_1 = self.entry_a.get().strip()  # valor a escribir
        id_2 = self.entry_b.get().strip()  # columna

        if not id_1 or not id_2:
            return

        id_1 = int(id_1, 16)
        col_index = int(id_2) - 1

        if not (0 <= id_1 <= 0xFF):
            raise ValueError(t("ui_remap_id.error_id1"))

        if not (0 <= col_index <= 3):  # columnas 0..3
            raise ValueError(t("ui_remap_id.error_id2"))

        data = self.get_table_values()

        for fil in data:
            if col_index < len(fil):  # verificar que exista esa columna
                fil[col_index] = id_1

        self.set_table_values(data)

    @error_window_ui
    def aplicar_cambios(self):
        data = self.get_table_values()
        self.master.reemplazar_id_bones(data)


    # ==================================
    # SELECCIONAR FILA
    # ==================================

    def _select_row(self, index):

        if self.selected_row is not None:

            prev = self.selected_row
            row_color = self.color_normal if prev % 2 == 0 else self.color_alt

            for widget in self.rows[prev]:
                widget.configure(fg_color=row_color)

        self.selected_row = index

        for widget in self.rows[index]:
            widget.configure(fg_color=self.color_selected)

    # ==================================
    # LIMPIAR TABLA
    # ==================================

    def clear_table(self):

        for row in self.rows:
            for w in row:
                w.destroy()

        self.rows.clear()
        self.selected_row = None

    # ==================================
    # CARGAR DATOS
    # ==================================

    def set_table_values(self, data):

        self.clear_table()

        for i, values in enumerate(data):

            row_widgets = []

            # asegurar máximo 4 valores
            values = values[:4]

            # rellenar los que faltan con None
            padded_values = values + [None] * (4 - len(values))

            row_data = [i] + padded_values

            for col, value in enumerate(row_data):

                row_color = self.color_normal if i % 2 == 0 else self.color_alt

                entry = ctk.CTkEntry(
                    self.table,
                    width=55,
                    justify="center",
                    fg_color=row_color,
                    font=GRID_FONT
                )

                # columna N°
                if col == 0:
                    entry.insert(0, f"{value:02}")
                    entry.configure(state="disabled")

                else:

                    if value is None:
                        entry.insert(0, "00")
                        entry.configure(state="disabled")
                    else:
                        entry.insert(0, f"{value:02X}")

                entry.grid(row=i, column=col, padx=2, pady=1)

                entry.bind(
                    "<Button-1>",
                    lambda e, r=i: self._select_row(r)
                )

                row_widgets.append(entry)

            self.rows.append(row_widgets)

    # ==================================
    # OBTENER VALORES DE LA TABLA
    # ==================================

    def get_table_values(self) -> list[int]:

        data = []

        for row in self.rows:

            values = []

            for col, entry in enumerate(row):

                # saltar columna N°
                if col == 0:
                    continue

                # ignorar entries bloqueados
                if entry.cget("state") == "disabled":
                    continue

                try:
                    values.append(int(entry.get(), 16))
                except ValueError:
                    values.append(0)

            data.append(values)

        return data