import customtkinter as ctk
import traceback
import functools

from app.utils import center_window


def error_window_ui(func):
    """
    Wrapper que ejecuta una función y si falla
    muestra una ventana con el error completo.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except Exception:
            error_texto = traceback.format_exc()

            # Ventana de error
            win = ctk.CTkToplevel()
            win.title("Error")
            win.geometry("700x450")
            win.grab_set()  # modal
            center_window(win, 700, 450)

            frame = ctk.CTkFrame(win)
            frame.pack(fill="both", expand=True, padx=10, pady=10)

            label = ctk.CTkLabel(frame, text="Se produjo un error:", anchor="w")
            label.pack(fill="x", padx=5, pady=(5, 0))

            # Textbox con scroll automático
            textbox = ctk.CTkTextbox(frame, wrap="none")
            textbox.pack(fill="both", expand=True, padx=5, pady=5)

            textbox.insert("1.0", error_texto)
            textbox.configure(state="disabled")

            btn = ctk.CTkButton(frame, text="Cerrar", command=win.destroy)
            btn.pack(pady=5)

    return wrapper
