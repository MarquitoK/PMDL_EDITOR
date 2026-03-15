import sys
import os
import subprocess
import customtkinter as ctk
from app.utils.lang import t, save_lang, get_current_lang, AVAILABLE_LANGS
from app.utils.window import center_window


class LangWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title(t("lang_window.titulo"))
        self.resizable(False, False)
        self.grab_set()
        center_window(self, 300, 200)

        self._selected = get_current_lang()

        ctk.CTkLabel(self, text=t("lang_window.descripcion"), font=("Segoe UI", 13)).pack(pady=(20, 10))

        self._radio_var = ctk.StringVar(value=self._selected)
        for code, label in AVAILABLE_LANGS.items():
            ctk.CTkRadioButton(
                self, text=label, variable=self._radio_var, value=code,
                font=("Segoe UI", 12)
            ).pack(anchor="w", padx=40, pady=2)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(16, 10))

        ctk.CTkButton(
            btn_frame, text=t("lang_window.btn_aplicar"), width=100,
            command=self._on_apply
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text=t("lang_window.btn_cancelar"), width=100,
            fg_color="gray40", hover_color="gray30",
            command=self.destroy
        ).pack(side="left", padx=8)

    def _on_apply(self):
        chosen = self._radio_var.get()
        if chosen == get_current_lang():
            self.destroy()
            return

        self.destroy()
        self._show_restart_dialog(chosen)

    def _show_restart_dialog(self, lang_code: str):
        dlg = ctk.CTkToplevel(self.master)
        dlg.title(t("lang_window.reinicio_titulo"))
        dlg.resizable(False, False)
        dlg.grab_set()
        center_window(dlg, 340, 140)

        ctk.CTkLabel(
            dlg, text=t("lang_window.reinicio_msg"),
            font=("Segoe UI", 12), wraplength=300
        ).pack(pady=(24, 16))

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack()

        def _ok():
            save_lang(lang_code)
            dlg.destroy()
            _restart_app()

        ctk.CTkButton(
            btn_frame, text=t("lang_window.btn_ok"), width=90,
            command=_ok
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text=t("lang_window.btn_cancelar_reinicio"), width=90,
            fg_color="gray40", hover_color="gray30",
            command=dlg.destroy
        ).pack(side="left", padx=8)


def _restart_app():
    python = sys.executable
    script = os.path.abspath(sys.argv[0])
    subprocess.Popen([python, script])
    sys.exit(0)
