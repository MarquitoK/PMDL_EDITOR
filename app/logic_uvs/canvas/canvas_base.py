from tkinter import Canvas

from ..ui_components import VERT_RADIUS


class UVCanvasBase(Canvas):
    """Clase base del canvas UV - maneja inicialización, zoom y pan"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # Textura
        self.texture_image = None
        self.texture_photo = None
        self.texture_base  = None   # Caché 512×512 RGBA

        # Elementos canvas
        self.uv_points  = []
        self.uv_lines   = []
        self.uv_faces   = []
        self.face_items = []
        self.face_centers = []

        # Datos lógicos
        self.uv_data  = []
        self.tri_data = []
        self.selected_points = []

        # Zoom / pan
        self.zoom_level  = 1.0
        self.pan_x       = 0
        self.pan_y       = 0
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.is_panning  = False

        # Box-select
        self.selection_rect    = None
        self.selection_start_x = 0
        self.selection_start_y = 0
        self.is_selecting      = False

        # G-mode
        self.g_mode          = False
        self.g_axis          = None
        self.g_num_str       = ""
        self.g_mouse_start_x = 0
        self.g_mouse_start_y = 0
        self.g_saved_pos     = {}
        self._g_accum_x      = 0.0
        self._g_accum_y      = 0.0

        # S-mode (escalado)
        self.s_mode          = False
        self.s_axis          = None
        self.s_num_str       = ""
        self.s_mouse_start_x = 0
        self.s_mouse_start_y = 0
        self.s_saved_pos     = {}
        self.s_center_x      = 128
        self.s_center_y      = 128

        # Undo/Redo stack
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo   = 50

        self._mouse_x = 0
        self._mouse_y = 0

        self.selection_mode = 'vertex'
        self.coord_label = None

        # throttle de zoom
        self._zoom_pending   = False
        self._zoom_after_id  = None
        # caché de textura: evita PIL resize si render_size no cambió
        self._texture_cache_size  = None
        self._texture_cache_photo = None

        self._create_mode_ui()

    # helpers

    def _grab_focus(self, event):
        self.focus_set()

    def _get_scale(self):
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1: w = 512
        if h <= 1: h = 512
        base   = min(w, h)
        logical = base * self.zoom_level
        capped  = min(logical, 4096)
        return (capped / 256.0)

    def _uv_to_screen(self, uv_x, uv_y):
        s = self._get_scale()
        return uv_x * s + self.pan_x, uv_y * s + self.pan_y

    # zoom / pan

    def on_zoom(self, event):
        if not self.texture_image:
            return
        step     = 0.24 if event.delta > 0 else -0.24
        new_zoom = self.zoom_level + step
        if new_zoom < 0.25 or new_zoom > 16.0:
            return
        factor          = new_zoom / self.zoom_level
        self.pan_x      = event.x - (event.x - self.pan_x) * factor
        self.pan_y      = event.y - (event.y - self.pan_y) * factor
        self.zoom_level = new_zoom
        self._zoom_pending = True
        if not getattr(self, '_zoom_after_id', None):
            self._zoom_after_id = self.after(16, self._flush_zoom)

    def _flush_zoom(self):
        self._zoom_after_id = None
        if not getattr(self, '_zoom_pending', False):
            return
        self._zoom_pending = False
        self._fast_redraw()

    def on_pan_start(self, event):
        self.is_panning  = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def on_pan_drag(self, event):
        if not self.is_panning:
            return
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.pan_x      += dx
        self.pan_y      += dy
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        # Pan: mover todos los items del canvas juntos, sin tocar PIL
        self.move("all", dx, dy)
        self.delete("edge_grad")
        if hasattr(self, '_refresh_colors'):
            self._refresh_colors()

    def on_pan_release(self, event):
        self.is_panning = False

    def _fast_redraw(self):
        if not self.texture_image:
            return
        old_scale = self._get_scale()
        self.redraw_texture()
        self._reposition_all_uvs(old_scale, self.pan_x, self.pan_y)

    # ── undo/redo ─────────────────────────────────────────────────────────────

    def _push_undo_snapshot(self):
        """Guarda el estado actual en el stack de undo"""
        if not self.uv_data:
            return
        
        # Crear snapshot de las posiciones de todos los vértices
        snapshot = []
        for d in self.uv_data:
            snapshot.append({
                'vertex': d['vertex'],
                'x': d['vertex']['x'],
                'y': d['vertex']['y']
            })
        
        self.undo_stack.append(snapshot)
        
        # Limitar tamaño del stack
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        
        # Limpiar redo stack al hacer una acción nueva
        self.redo_stack.clear()

    def _undo(self):
        """Deshace la última acción"""
        if not self.undo_stack:
            print("No hay acciones para deshacer")
            return
        
        # Guardar estado actual en redo stack ANTES de deshacer
        current_snapshot = []
        for d in self.uv_data:
            current_snapshot.append({
                'vertex': d['vertex'],
                'x': d['vertex']['x'],
                'y': d['vertex']['y']
            })
        self.redo_stack.append(current_snapshot)
        
        # Restaurar estado anterior
        snapshot = self.undo_stack.pop()
        scale = self._get_scale()
        
        for saved in snapshot:
            saved['vertex']['x'] = saved['x']
            saved['vertex']['y'] = saved['y']
        
        # Actualizar visualización
        for d in self.uv_data:
            self._update_point_and_lines(d, scale)
        self._update_faces()
        self.delete("edge_grad")
        self._refresh_colors()
        self._update_coord_label()
        print(f"Undo aplicado ({len(self.undo_stack)} estados restantes)")
        
        # Auto-guardar para actualizar visor 3D
        if hasattr(self, 'editor'):
            self.editor.mark_as_modified()
            self.editor.auto_save_preview()

    def _redo(self):
        """Rehace la última acción deshecha"""
        if not self.redo_stack:
            print("No hay acciones para rehacer")
            return
        
        # Guardar estado actual en undo stack ANTES de rehacer
        current_snapshot = []
        for d in self.uv_data:
            current_snapshot.append({
                'vertex': d['vertex'],
                'x': d['vertex']['x'],
                'y': d['vertex']['y']
            })
        self.undo_stack.append(current_snapshot)
        
        # Restaurar estado de redo
        snapshot = self.redo_stack.pop()
        scale = self._get_scale()
        
        for saved in snapshot:
            saved['vertex']['x'] = saved['x']
            saved['vertex']['y'] = saved['y']
        
        # Actualizar visualización
        for d in self.uv_data:
            self._update_point_and_lines(d, scale)
        self._update_faces()
        self.delete("edge_grad")
        self._refresh_colors()
        self._update_coord_label()
        print(f"Redo aplicado ({len(self.redo_stack)} redos restantes)")
        
        # Auto-guardar para actualizar visor 3D
        if hasattr(self, 'editor'):
            self.editor.mark_as_modified()
            self.editor.auto_save_preview()