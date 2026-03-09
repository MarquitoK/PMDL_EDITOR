import customtkinter as ctk
import traceback
import functools

from app.utils import center_window
from app.utils.icon import set_app_icon


def error_window_ui(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except Exception:
            error_texto = traceback.format_exc()

            win = ctk.CTkToplevel()
            win.title("Error")
            win.geometry("700x450")
            win.grab_set()
            center_window(win, 700, 450)
            set_app_icon(win)

            frame = ctk.CTkFrame(win)
            frame.pack(fill="both", expand=True, padx=10, pady=10)

            label = ctk.CTkLabel(frame, text="Se produjo un error:", anchor="w")
            label.pack(fill="x", padx=5, pady=(5, 0))

            textbox = ctk.CTkTextbox(frame, wrap="none")
            textbox.pack(fill="both", expand=True, padx=5, pady=5)

            textbox.insert("1.0", error_texto)
            textbox.configure(state="disabled")

            btn = ctk.CTkButton(frame, text="Cerrar", command=win.destroy)
            btn.pack(pady=5)

    return wrapper