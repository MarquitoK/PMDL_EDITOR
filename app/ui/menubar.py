import tkinter as tk
import customtkinter as ctk


class MenuBar(ctk.CTkFrame):
    """Menu bar personalizado para customtkinter."""
    
    def __init__(self, master, **kwargs):
        # Extraer height si viene en kwargs, sino usar 28 por defecto
        height = kwargs.pop('height', 28)
        super().__init__(master, corner_radius=0, height=height, **kwargs)
        self.pack_propagate(False)  # CRÍTICO: evita que se expanda
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
        
        # Botón del menú - Fuente 11pt
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
        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height()
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
                # Crear frame para comando con label y accelerator
                cmd_frame = ctk.CTkFrame(container, fg_color="transparent")
                cmd_frame.pack(fill="x", padx=0, pady=0)
                
                # Texto del comando (alineado a la izquierda)
                cmd_text = item["label"]
                accelerator = item.get("accelerator", "")
                
                if accelerator:
                    # Botón con label y shortcut
                    btn = ctk.CTkButton(
                        cmd_frame,
                        text=f"{cmd_text:<25} {accelerator:>15}",
                        width=180,
                        height=28,
                        corner_radius=3,
                        font=("Segoe UI", 11),
                        fg_color="transparent",
                        hover_color=("gray75", "gray25"),
                        anchor="w",
                        command=lambda cmd=item["command"]: self._execute_command(cmd)
                    )
                else:
                    # Botón sin shortcut
                    btn = ctk.CTkButton(
                        cmd_frame,
                        text=cmd_text,
                        width=180,
                        height=28,
                        corner_radius=3,
                        font=("Segoe UI", 11),
                        fg_color="transparent",
                        hover_color=("gray75", "gray25"),
                        anchor="w",
                        command=lambda cmd=item["command"]: self._execute_command(cmd)
                    )
                btn.pack(fill="x", padx=3, pady=1)
        
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