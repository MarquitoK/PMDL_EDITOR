import customtkinter as ctk

from app.utils.icon import set_app_icon

ZEBRA_A = "#2B2B2B"
ZEBRA_B = "#242424"

class ScrollableOptionMenu(ctk.CTkFrame):
    def __init__(self, master, values=None, width=160,
                 command=None, name_window="Select option", **kwargs):
        super().__init__(master, **kwargs)

        self.values = values or []
        self.command = command
        self._current_value = None
        self.name_window = name_window

        self.button = ctk.CTkButton(
            self,
            text="Selec",
            width=width,
            command=self._open_menu
        )
        self.button.pack(fill="x")

    # =========================
    # API COMPATIBLE
    # =========================
    def configure(self, **kwargs):
        if "values" in kwargs:
            self.set_values(kwargs["values"])
        super().configure(**{k: v for k, v in kwargs.items() if k != "values"})

    def cget(self, key):
        if key == "values":
            return self.values
        return super().cget(key)

    def set(self, value):
        if value not in self.values:
            return
        self._current_value = value
        self.button.configure(text=value)

    def get(self):
        return self._current_value

    # =========================
    # INTERNOS
    # =========================
    def set_values(self, values):
        self.values = list(values)
        if values:
            self.set(values[0])

    def _open_menu(self):
        win = ctk.CTkToplevel(self)
        win.title(self.name_window)

        win.resizable(False, False)  # ← evita redimensionar
        width, height = 220, 300
        set_app_icon(win)

        # 🔹 POSICIÓN DEL MOUSE (ABSOLUTA)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()

        # 🔹 LÍMITES DE PANTALLA (evita que se salga)
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()

        if x + width > screen_w:
            x = screen_w - width
        if y + height > screen_h:
            y = screen_h - height

        win.geometry(f"{width}x{height}+{x}+{y}")

        win.transient(self.winfo_toplevel())
        win.grab_set()

        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        for i, value in enumerate(self.values):
            row_color = ZEBRA_A if i % 2 == 0 else ZEBRA_B

            btn = ctk.CTkButton(
                scroll,
                text=value,
                anchor="center",
                fg_color=row_color,
                hover_color="#3A3A3A",
                command=lambda v=value: self._select(v, win)
            )

            btn.pack(fill="x", padx=2, pady=0)

    def _select(self, value, win):
        self.set(value)
        win.destroy()
        if self.command:
            self.command(value)
