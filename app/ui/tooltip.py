from ast import Str

import customtkinter as ctk

class ToolTip:
    def __init__(self, widget, text:str):
        self.widget = widget
        self.text = text
        self.tip = None

        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def change_text(self, text:str):
        self.text = text

    def show(self, event=None):
        if self.tip:
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

    def hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None
