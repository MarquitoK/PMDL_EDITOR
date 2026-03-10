class UVCanvasGMode:
    
    def _g_start(self):
        if not self.selected_points:
            return
        # Guardar snapshot ANTES de empezar a mover
        self._push_undo_snapshot()
        
        self.g_mode          = True
        self.g_axis          = None
        self.g_num_str       = ""
        self.g_mouse_start_x = self._mouse_x
        self.g_mouse_start_y = self._mouse_y
        self._g_accum_x      = 0.0
        self._g_accum_y      = 0.0
        self.g_saved_pos = {}
        for d in self.uv_data:
            if d['point'] in self.selected_points:
                self.g_saved_pos[d['point']] = (d['vertex']['x'], d['vertex']['y'])

    def _g_move_free(self, mouse_x, mouse_y):
        """Mueve según el mouse con acumulador sub-pixel"""
        scale  = self._get_scale()
        raw_dx = (mouse_x - self.g_mouse_start_x) / scale
        raw_dy = (mouse_y - self.g_mouse_start_y) / scale
        int_dx = int(raw_dx)
        int_dy = int(raw_dy)

        for d in self.uv_data:
            if d['point'] not in self.g_saved_pos:
                continue
            ox, oy = self.g_saved_pos[d['point']]
            if self.g_axis == 'x':
                d['vertex']['x'] = max(0, min(255, ox + int_dx))
                d['vertex']['y'] = oy
            elif self.g_axis == 'y':
                d['vertex']['x'] = ox
                d['vertex']['y'] = max(0, min(255, oy + int_dy))
            else:
                d['vertex']['x'] = max(0, min(255, ox + int_dx))
                d['vertex']['y'] = max(0, min(255, oy + int_dy))
            self._update_point_and_lines(d, scale)
        self._update_faces()
        self.delete("edge_grad")
        self._edge_grad_dirty = True
        self._prev_sel_set = None
        self._refresh_colors()
        self._update_coord_label()

    def _g_apply_numeric(self):
        """Aplica posición absoluta (0-255)"""
        if not self.g_num_str:
            return
        try:
            val = max(0, min(255, int(self.g_num_str)))
        except ValueError:
            return
        scale = self._get_scale()
        for d in self.uv_data:
            if d['point'] not in self.g_saved_pos:
                continue
            ox, oy = self.g_saved_pos[d['point']]
            if self.g_axis == 'x':
                d['vertex']['x'] = val
                d['vertex']['y'] = oy
            elif self.g_axis == 'y':
                d['vertex']['x'] = ox
                d['vertex']['y'] = val
            self._update_point_and_lines(d, scale)
        self._update_faces()
        self._refresh_colors()
        self._update_coord_label()

    def _g_apply(self):
        """Confirma el G-mode"""
        self.g_mode      = False
        self.g_axis      = None
        self.g_num_str   = ""
        self.g_saved_pos = {}
        
        # Marcar como modificado y auto-guardar
        if hasattr(self, 'editor'):
            self.editor.mark_as_modified()
            self.editor.auto_save_preview()

    def _g_cancel(self):
        """Cancela G-mode restaurando posiciones"""
        scale = self._get_scale()
        for d in self.uv_data:
            if d['point'] in self.g_saved_pos:
                ox, oy = self.g_saved_pos[d['point']]
                d['vertex']['x'] = ox
                d['vertex']['y'] = oy
                self._update_point_and_lines(d, scale)
        self._update_faces()
        self.delete("edge_grad")
        self._edge_grad_dirty = True
        self._prev_sel_set = None
        self._refresh_colors()
        self.g_mode      = False
        self.g_axis      = None
        self.g_num_str   = ""
        self.g_saved_pos = {}