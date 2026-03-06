def center_window(window, width: int, height: int):
    """
    Centra una ventana en la pantalla.
    """
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    
    x = (screen_w // 2) - (width // 2)
    y = (screen_h // 2) - (height // 2)
    
    window.geometry(f"{width}x{height}+{x}+{y}")

def center_to_window(window, parent):
    window.update_idletasks()

    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()

    w = window.winfo_width()
    h = window.winfo_height()

    x = px + (pw // 2 - w // 2)
    y = py + (ph // 2 - h // 2)

    window.geometry(f"+{x}+{y}")