import sys
import os
import customtkinter as ctk
from app.utils.lang import t, save_lang, get_current_lang, AVAILABLE_LANGS
from app.utils.window import center_window
from app.utils.icon import set_app_icon

# Mensajes de cierre en cada idioma (hardcodeados para mostrarse en el idioma destino)
_CLOSE_MSGS = {
    "es": ("Idioma guardado", "El idioma fue guardado.\nCierra y vuelve a abrir la aplicación para aplicar los cambios."),
    "en": ("Language saved", "The language has been saved.\nClose and reopen the application to apply the changes."),
    "pt_br": ("Idioma salvo", "O idioma foi salvo.\nFeche e abra novamente o aplicativo para aplicar as alterações."),
}

_CLOSE_BTN = {
    "es": "Cerrar aplicación",
    "en": "Close application",
    "pt_br": "Fechar aplicativo",
}


class LangWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title(t("lang_window.titulo"))
        self.resizable(False, False)
        self.grab_set()
        set_app_icon(self)
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

        save_lang(chosen)
        self.destroy()
        self._show_close_dialog(chosen)

    def _show_close_dialog(self, lang_code: str):
        title, msg = _CLOSE_MSGS.get(lang_code, _CLOSE_MSGS["es"])
        btn_text = _CLOSE_BTN.get(lang_code, _CLOSE_BTN["es"])

        dlg = ctk.CTkToplevel(self.master)
        dlg.title(title)
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)
        set_app_icon(dlg)
        center_window(dlg, 360, 150)

        ctk.CTkLabel(
            dlg, text=msg,
            font=("Segoe UI", 12), wraplength=320
        ).pack(pady=(24, 16))

        ctk.CTkButton(
            dlg, text=btn_text, width=160,
            command=self.master.destroy
        ).pack()