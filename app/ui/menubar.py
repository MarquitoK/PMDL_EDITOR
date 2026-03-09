import tkinter as tk
import customtkinter as ctk


class MenuBar(ctk.CTkFrame):
    """Menu bar personalizado para customtkinter."""
    
    def __init__(self, master, **kwargs):
        height = kwargs.pop('height', 28)
        super().__init__(master, corner_radius=0, height=height, **kwargs)
        self.pack_propagate(False)
        self.menus = {}
        self.active_dropdown = None
        
    def add_menu(self, label: str) -> 'Menu':
        """Agrega un menú al menu bar."""
        menu = Menu(self, label)
        menu.pack(side="left", padx=0, pady=0)
        self.menus[label] = menu
        return menu


class Menu(ctk.CTkFrame):
    """Menú individual con dropdown."""
    
    def __init__(self, menubar: MenuBar, label: str):
        super().__init__(menubar, fg_color="transparent")
        self.menubar = menubar
        self.label = label
        self.dropdown = None
        self.commands = []
        
        # Botón del menú
        self.button = ctk.CTkButton(
            self, 
            text=label, 
            width=70,
            height=22,
            corner_radius=3,
            font=("Segoe UI", 11),
            fg_color="transparent",
            hover_color=("gray75", "gray25"),
            command=self._toggle_dropdown
        )
        self.button.pack(padx=1, pady=1)
        
    def add_command(self, label: str, command=None, accelerator: str = None):
        """Agrega un comando al menú."""
        self.commands.append({"label": label, "command": command, "accelerator": accelerator})
        
    def add_separator(self):
        """Agrega un separador al menú."""
        self.commands.append({"separator": True})
        
    def _toggle_dropdown(self):
        """Muestra u oculta el dropdown."""
        if self.dropdown and self.dropdown.winfo_exists():
            self._close_dropdown()
        else:
            # Cerrar cualquier otro dropdown abierto
            if self.menubar.active_dropdown:
                self.menubar.active_dropdown._close_dropdown()
            
            self._show_dropdown()
            self.menubar.active_dropdown = self
    
    def _show_dropdown(self):
        """Muestra el dropdown."""
        # Crear ventana toplevel
        self.dropdown = tk.Toplevel(self)
        self.dropdown.overrideredirect(True)
        self.dropdown.configure(bg=self._get_dropdown_bg())
        
        # Posicionar debajo del botón
        button_x = self.button.winfo_rootx()
        button_y = self.button.winfo_rooty()
        button_height = self.button.winfo_height()
        button_width = self.button.winfo_width()
        screen_width = self.winfo_screenwidth()
        
        # Ancho del dropdown (ajustado para los shortcuts)
        dropdown_width = 230
        
        # Calcular posición X del borde derecho del botón
        button_right_edge = button_x + button_width
        
        # Decidir si abrir a la izquierda o derecha
        if button_right_edge + dropdown_width > screen_width:
            x = button_right_edge - dropdown_width
        else:
            x = button_x
        
        y = button_y + button_height
        self.dropdown.geometry(f"+{x}+{y}")
        
        # Frame contenedor
        container = ctk.CTkFrame(
            self.dropdown,
            corner_radius=4,
            border_width=1,
            border_color=("gray70", "gray30")
        )
        container.pack(fill="both", expand=True)
        
        # Agregar comandos
        for item in self.commands:
            if item.get("separator"):
                sep = ctk.CTkFrame(container, height=1, fg_color=("gray70", "gray30"))
                sep.pack(fill="x", padx=4, pady=2)
            else:
                accelerator = item.get("accelerator", "")
                cmd_text    = item["label"]

                # Frame de fila con grid para alinear label y shortcut
                cmd_frame = ctk.CTkFrame(container, fg_color="transparent", corner_radius=3)
                cmd_frame.pack(fill="x", padx=3, pady=1)
                cmd_frame.grid_columnconfigure(0, weight=1)
                cmd_frame.grid_columnconfigure(1, weight=0)

                def _make_hover(frame, lbl, acc_lbl=None):
                    hover = ctk.ThemeManager.theme["CTkButton"]["hover_color"]
                    if isinstance(hover, list):
                        hover_dark  = hover[1]
                        hover_light = hover[0]
                    else:
                        hover_dark = hover_light = hover

                    def on_enter(e):
                        mode = ctk.get_appearance_mode()
                        c = hover_dark if mode == "Dark" else hover_light
                        frame.configure(fg_color=c)
                    def on_leave(e):
                        frame.configure(fg_color="transparent")

                    frame.bind("<Enter>", on_enter)
                    frame.bind("<Leave>", on_leave)
                    lbl.bind("<Enter>", on_enter)
                    lbl.bind("<Leave>", on_leave)
                    if acc_lbl:
                        acc_lbl.bind("<Enter>", on_enter)
                        acc_lbl.bind("<Leave>", on_leave)

                lbl = ctk.CTkLabel(
                    cmd_frame,
                    text=f"  {cmd_text}",
                    font=("Segoe UI", 11),
                    anchor="w",
                    height=28,
                )
                lbl.grid(row=0, column=0, sticky="ew")

                acc_lbl = None
                if accelerator:
                    acc_lbl = ctk.CTkLabel(
                        cmd_frame,
                        text=f"{accelerator}  ",
                        font=("Segoe UI", 10),
                        anchor="e",
                        height=28,
                        text_color=("gray50", "gray55"),
                    )
                    acc_lbl.grid(row=0, column=1, sticky="e")

                _make_hover(cmd_frame, lbl, acc_lbl)

                # Clic en el frame o en cualquier label ejecuta el comando
                _cmd = item["command"]
                for widget in [cmd_frame, lbl] + ([acc_lbl] if acc_lbl else []):
                    widget.bind("<Button-1>", lambda e, c=_cmd: self._execute_command(c))
        
        # Bind para cerrar al hacer clic fuera
        self.dropdown.bind("<FocusOut>", lambda e: self._close_dropdown())
        self.dropdown.focus_set()
        
        # Bind para cerrar con Escape
        self.dropdown.bind("<Escape>", lambda e: self._close_dropdown())
    
    def _close_dropdown(self):
        """Cierra el dropdown."""
        if self.dropdown and self.dropdown.winfo_exists():
            self.dropdown.destroy()
        self.dropdown = None
        if self.menubar.active_dropdown == self:
            self.menubar.active_dropdown = None
    
    def _execute_command(self, command):
        """Ejecuta un comando y cierra el dropdown."""
        self._close_dropdown()
        if callable(command):
            command()
    
    def _get_dropdown_bg(self):
        """Obtiene el color de fondo del dropdown según el tema."""
        appearance = ctk.get_appearance_mode()
        if appearance == "Dark":
            return "#2b2b2b"
        else:
            return "#f0f0f0"