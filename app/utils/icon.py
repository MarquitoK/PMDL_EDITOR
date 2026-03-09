import os
import tkinter as tk
from tkinter import messagebox as _mb


def _get_icon_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "app", "resources", "icon.ico")


def set_app_icon(window) -> None:
    """
    Aplica el ícono a una ventana CTk / Toplevel.
    Usa after(200) para ejecutarse DESPUÉS de que CTkToplevel
    termine su propia inicialización (que borra el ícono heredado).
    """
    icon_path = _get_icon_path()

    def _apply():
        try:
            if os.path.exists(icon_path):
                window.iconbitmap(icon_path)
        except Exception as e:
            print(f"[icon] No se pudo aplicar ícono: {e}")

    window.after(200, _apply)


def _make_icon_parent(master=None) -> tk.Toplevel:
    icon_path = _get_icon_path()
    root = master if master else tk._default_root
    top = tk.Toplevel(root)
    top.withdraw()
    top.attributes("-alpha", 0)
    try:
        if os.path.exists(icon_path):
            top.iconbitmap(icon_path)
    except Exception:
        pass
    return top


def show_info(master, title: str, message: str) -> None:
    parent = _make_icon_parent(master)
    try:
        _mb.showinfo(title, message, parent=parent)
    finally:
        parent.destroy()


def show_error(master, title: str, message: str) -> None:
    parent = _make_icon_parent(master)
    try:
        _mb.showerror(title, message, parent=parent)
    finally:
        parent.destroy()


def show_warning(master, title: str, message: str) -> None:
    parent = _make_icon_parent(master)
    try:
        _mb.showwarning(title, message, parent=parent)
    finally:
        parent.destroy()


def ask_yesno(master, title: str, message: str) -> bool:
    parent = _make_icon_parent(master)
    try:
        return _mb.askyesno(title, message, parent=parent)
    finally:
        parent.destroy()