import os
import sys
import tkinter as tk
from tkinter import messagebox as _mb

_icon_path_cache: str = ""


def _get_icon_path() -> str:
    global _icon_path_cache
    if _icon_path_cache:
        return _icon_path_cache
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _icon_path_cache = os.path.join(base, "app", "resources", "icon.ico")
    return _icon_path_cache


def set_app_icon(window) -> None:
    icon_path = _get_icon_path()
    if not os.path.exists(icon_path):
        return

    if isinstance(window, tk.Tk) and not isinstance(window, tk.Toplevel):
        try:
            window.wm_iconbitmap(icon_path)
        except Exception as e:
            print(f"[icon] {e}")
        return

    _after_id = [None]

    def _apply():
        _after_id[0] = None
        try:
            if window.winfo_exists():
                window.wm_iconbitmap(icon_path)
        except Exception:
            pass

    def _on_destroy(event=None):
        if _after_id[0] is not None:
            try:
                window.after_cancel(_after_id[0])
            except Exception:
                pass
            _after_id[0] = None

    _after_id[0] = window.after(250, _apply)
    window.bind("<Destroy>", _on_destroy, add="+")


def _make_icon_parent(master=None) -> tk.Toplevel:
    icon_path = _get_icon_path()
    root = master if master else tk._default_root
    top = tk.Toplevel(root)
    top.withdraw()
    top.attributes("-alpha", 0)
    try:
        if os.path.exists(icon_path):
            top.wm_iconbitmap(icon_path)
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