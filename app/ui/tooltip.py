import customtkinter as ctk
from pathlib import Path

class ToolTip:
    def __init__(self, widget, text: str, timeout: int = 5000):
        self.widget = widget
        self.text = text
        self.tip = None
        self.timeout = timeout   # tiempo en ms
        self._after_id = None    # id del temporizador
        self._focus_check = None

        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<FocusOut>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

        widget.winfo_toplevel().bind("<FocusOut>", self.hide, add="+")
        widget.winfo_toplevel().bind("<Unmap>", self.hide, add="+")
        widget.winfo_toplevel().bind("<Leave>", self.hide, add="+")

    # ------------------------------

    def change_text(self, text: str):
        self.text = self._user_hide(text)

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

        # ⏱️ autocierre normal
        if self.timeout > 0 and not self._after_id:
            root = self.widget.winfo_toplevel()
            self._after_id = root.after(self.timeout, self.hide)

        # 👇 iniciar verificación global de foco
        self._check_focus_loop()

    # ------------------------------

    def hide(self, event=None):

        # cancelar timer de autocierre
        if self._after_id is not None and self.tip:
            try:
                root = self.widget.winfo_toplevel()
                root.after_cancel(self._after_id)
            except:
                pass
            self._after_id = None

        # cancelar loop de foco
        if self._focus_check is not None and self.tip:
            try:
                self.tip.after_cancel(self._focus_check)
            except:
                pass
            self._focus_check = None

        if self.tip is not None:
            try:
                self.tip.destroy()
            except:
                pass
            self.tip = None

    # ------------------------------

    def _user_hide(self, path_str: str) -> str:
        if not self._is_path_like(path_str):
            return path_str

        p = Path(path_str)
        home = Path.home()

        try:
            rel = p.relative_to(home)
            return f"{p.drive}\\~\\{rel}".replace("\\", "/")
        except ValueError:
            return path_str.replace("\\", "/")

    def _is_path_like(self, path_str: str) -> bool:
        try:
            return Path(path_str).anchor != "" or "/" in path_str or "\\" in path_str
        except Exception:
            return False

    def _check_focus_loop(self):
        if not self.tip:
            return

        try:
            # si la app ya no tiene foco → cerrar tooltip
            root = self.widget.winfo_toplevel()
            if root.focus_displayof() is None:
                self.hide()
                return
        except:
            self.hide()
            return

        if not self._after_id:
            self.hide()
            return

        # repetir cada 250 ms
        self._focus_check = self.tip.after(250, self._check_focus_loop)
