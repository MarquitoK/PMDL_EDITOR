"""
UI Components - Constantes visuales y componentes reutilizables
"""

# ──────────────────────────────────────────────────────────────────────────────
# Colores globales
# ──────────────────────────────────────────────────────────────────────────────
C_VERT_NORMAL = "#000000"   # Vértice sin seleccionar: negro
C_VERT_SEL    = "#FF7F00"   # Vértice seleccionado: naranja
C_EDGE_NORMAL = "#FFFFFF"   # Edge normal: blanco (con borde negro)
C_EDGE_SEL    = "#FF7F00"   # Edge completamente seleccionado
C_EDGE_HALF   = "#FF9F40"   # Mitad del degradado de edge parcial
C_FACE_SEL    = "#FF8C00"   # Color del relleno de cara seleccionada
FACE_STIPPLE  = "gray50"    # Patrón ~50% → relleno semitransparente sólido
VERT_RADIUS   = 2           # Radio en px del vértice (60% del anterior 3px)
EDGE_WIDTH    = 1           # Grosor de la línea blanca central del edge
EDGE_BORDER   = 3           # Grosor del borde negro (siempre > EDGE_WIDTH)