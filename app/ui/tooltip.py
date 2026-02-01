import customtkinter as ctk
from pathlib import Path

class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None

        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

        # NUEVOS BINDS GLOBALES IMPORTANTES
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<FocusOut>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

        # Cuando la app pierde foco (Alt+Tab, cambiar a Chrome, etc)
        widget.winfo_toplevel().bind("<FocusOut>", self.hide, add="+")
        widget.winfo_toplevel().bind("<Unmap>", self.hide, add="+")  # minimizar ventana

    # ------------------------------

    def change_text(self, text: str):
        self.text = self.__user_hide(text)

    # ------------------------------

    def show(self, event=None):
        if self.tip or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip = ctk.CTkToplevel(self.widget)
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)

        label = ctk.CTkLabel(
            self.tip,
            text=self.text,
            fg_color="#2b2b2b",
            text_color="white",
            corner_radius=6,
            padx=8,
            pady=4,
            font=("Segoe UI", 11)
        )
        label.pack()

        self.tip.geometry(f"+{x}+{y}")

    # ------------------------------

    def hide(self, event=None):
        if self.tip is not None:
            try:
                self.tip.destroy()
            except:
                pass
            self.tip = None

    # ------------------------------

    def __user_hide(self, path_str: str):
        p = Path(path_str)
        home = Path.home()

        try:
            rel = p.relative_to(home)
            return f"{p.drive}\\~\\{rel}".replace("\\", "/")
        except ValueError:
            return path_str.replace("\\", "/")
