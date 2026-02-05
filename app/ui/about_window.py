import tkinter as tk
import customtkinter as ctk
import webbrowser


class AboutWindow(ctk.CTkToplevel):
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("Acerca de PMDL Editor")
        self.geometry("550x520")
        self.resizable(False, False)
        
        # Centrar ventana
        self._center_window()
        
        # Frame scrolleable principal
        scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Título
        title_label = ctk.CTkLabel(
            scroll_frame,
            text="PMDL Editor",
            font=("Segoe UI", 28, "bold")
        )
        title_label.pack(pady=(5, 3))
        
        # Versión
        version_label = ctk.CTkLabel(
            scroll_frame,
            text="Versión 1.4.2",
            font=("Segoe UI", 13),
            text_color=("gray50", "gray60")
        )
        version_label.pack(pady=(0, 15))
        
        # Descripción
        desc_frame = ctk.CTkFrame(scroll_frame, corner_radius=8)
        desc_frame.pack(fill="x", padx=5, pady=(0, 15))
        
        desc_text = (
            "PMDL Editor es una herramienta de modding diseñada\n"
            "para facilitar la edición avanzada de archivos PMDL,\n"
            "el formato de modelos 3D utilizado en Dragon Ball Z:\n"
            "Tenkaichi Tag Team.\n\n"
            "Esta aplicación permite manipular de forma intuitiva\n"
            "y eficiente las partes del modelo, mallas, vértices,\n"
            "coordenadas UV y pesos de huesos, simplificando\n"
            "el proceso de modding y edición."
        )
        
        desc_label = ctk.CTkLabel(
            desc_frame,
            text=desc_text,
            font=("Segoe UI", 11),
            justify="center"
        )
        desc_label.pack(padx=15, pady=15)
        
        # Enlaces
        links_frame = ctk.CTkFrame(scroll_frame, corner_radius=8)
        links_frame.pack(fill="x", padx=5, pady=(0, 12))
        
        links_container = ctk.CTkFrame(links_frame, fg_color="transparent")
        links_container.pack(pady=12)
        
        github_btn = ctk.CTkButton(
            links_container,
            text="🔗 GitHub",
            width=130,
            height=30,
            font=("Segoe UI", 11),
            command=lambda: self._open_url("https://github.com/MarquitoK/PMDL_EDITOR")
        )
        github_btn.pack(side="left", padx=4)
        
        youtube_btn = ctk.CTkButton(
            links_container,
            text="🎥 Los ijue30s",
            width=130,
            height=30,
            font=("Segoe UI", 11),
            command=lambda: self._open_url("https://www.youtube.com/@los-ijue30s")
        )
        youtube_btn.pack(side="left", padx=4)
        
        # Contribución
        contrib_frame = ctk.CTkFrame(scroll_frame, corner_radius=8)
        contrib_frame.pack(fill="x", padx=5, pady=(0, 12))
        
        contrib_title = ctk.CTkLabel(
            contrib_frame,
            text="Contribución",
            font=("Segoe UI", 13, "bold")
        )
        contrib_title.pack(pady=(12, 4))
        
        contrib_desc = ctk.CTkLabel(
            contrib_frame,
            text="Colaborador principal y clave en el desarrollo\nde la herramienta.",
            font=("Segoe UI", 10),
            text_color=("gray50", "gray60")
        )
        contrib_desc.pack(pady=(0, 8))
        
        kasto_btn = ctk.CTkButton(
            contrib_frame,
            text="🔧 KASTO MD ダ",
            width=170,
            height=30,
            font=("Segoe UI", 11),
            command=lambda: self._open_url("https://www.youtube.com/@KASTOMODDER15")
        )
        kasto_btn.pack(pady=(0, 12))
        
        # Agradecimientos
        thanks_frame = ctk.CTkFrame(scroll_frame, corner_radius=8)
        thanks_frame.pack(fill="x", padx=5, pady=(0, 10))
        
        thanks_title = ctk.CTkLabel(
            thanks_frame,
            text="Agradecimientos Especiales",
            font=("Segoe UI", 13, "bold")
        )
        thanks_title.pack(pady=(12, 4))
        
        thanks_desc = ctk.CTkLabel(
            thanks_frame,
            text="Por proporcionar información técnica esencial\nsobre la estructura del formato PMDL.",
            font=("Segoe UI", 10),
            text_color=("gray50", "gray60")
        )
        thanks_desc.pack(pady=(0, 8))
        
        migeru_btn = ctk.CTkButton(
            thanks_frame,
            text="📚 migeru_ao",
            width=170,
            height=30,
            font=("Segoe UI", 11),
            command=lambda: self._open_url("https://www.youtube.com/@migeru_ao")
        )
        migeru_btn.pack(pady=(0, 12))
        
        # Hacer modal
        self.transient(parent)
        self.grab_set()
        self.focus_set()
    
    def _center_window(self):
        self.update_idletasks()
        width = 550
        height = 520
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
    
    def _open_url(self, url: str):
        """Abre una URL en el navegador."""
        webbrowser.open(url)