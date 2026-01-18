def center_window(window, width: int, height: int):
    """
    Centra una ventana en la pantalla.
    """
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    
    x = (screen_w // 2) - (width // 2)
    y = (screen_h // 2) - (height // 2)
    
    window.geometry(f"{width}x{height}+{x}+{y}")