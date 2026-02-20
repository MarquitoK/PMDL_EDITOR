class UVCanvasSMode:
    
    def _s_start(self):
        """Inicia S-mode"""
        if not self.selected_points:
            return
        
        # Guardar snapshot ANTES de empezar a escalar
        self._push_undo_snapshot()
        
        self.s_mode          = True
        self.s_axis          = None
        self.s_num_str       = ""
        self.s_mouse_start_x = self._mouse_x
        self.s_mouse_start_y = self._mouse_y
        self.s_saved_pos     = {}
        
        # Calcular centro del grupo seleccionado
        sum_x, sum_y, count = 0, 0, 0
        for d in self.uv_data:
            if d['point'] in self.selected_points:
                sum_x += d['vertex']['x']
                sum_y += d['vertex']['y']
                count += 1
                self.s_saved_pos[d['point']] = (d['vertex']['x'], d['vertex']['y'])
        
        if count > 0:
            self.s_center_x = sum_x / count
            self.s_center_y = sum_y / count
        else:
            self.s_center_x = 128
            self.s_center_y = 128

    def _s_move_free(self, mouse_x, mouse_y):
        """
        Escala según el movimiento del mouse.
        Movimiento hacia derecha/arriba = escala mayor
        Movimiento hacia izquierda/abajo = escala menor
        """
        scale_canvas = self._get_scale()
        
        # Calcular factor de escala basado en distancia del mouse
        dx = (mouse_x - self.s_mouse_start_x) / 100.0
        dy = (mouse_y - self.s_mouse_start_y) / 100.0
        
        # Factor de escala: 1.0 + movimiento
        if self.s_axis == 'x':
            scale_factor_x = 1.0 + dx
            scale_factor_y = 1.0
        elif self.s_axis == 'y':
            scale_factor_x = 1.0
            scale_factor_y = 1.0 + dy
        else:
            # Sin eje fijado: usar promedio de ambos ejes
            avg = (dx + dy) / 2.0
            scale_factor_x = 1.0 + avg
            scale_factor_y = 1.0 + avg
        
        # Aplicar escala a cada vértice seleccionado
        for d in self.uv_data:
            if d['point'] not in self.s_saved_pos:
                continue
            
            ox, oy = self.s_saved_pos[d['point']]
            
            # Vector desde el centro al vértice original
            vec_x = ox - self.s_center_x
            vec_y = oy - self.s_center_y
            
            # Escalar el vector
            new_vec_x = vec_x * scale_factor_x
            new_vec_y = vec_y * scale_factor_y
            
            # Nueva posición = centro + vector escalado
            new_x = self.s_center_x + new_vec_x
            new_y = self.s_center_y + new_vec_y
            
            # Clamp a rango válido
            d['vertex']['x'] = max(0, min(255, int(new_x)))
            d['vertex']['y'] = max(0, min(255, int(new_y)))
            
            self._update_point_and_lines(d, scale_canvas)
        
        self._update_faces()
        self._refresh_colors()
        self._update_coord_label()

    def _s_apply_numeric(self):
        """
        Aplica factor de escala numérico absoluto.
        1.0 = tamaño original
        2.0 = doble de tamaño
        0.5 = mitad de tamaño
        -1.0 = invertido (espejo)
        """
        if not self.s_num_str:
            return
        
        try:
            # Permitir valores negativos y decimales
            if self.s_num_str == '-':
                scale_factor = -1.0
            elif '.' in self.s_num_str:
                scale_factor = float(self.s_num_str)
            else:
                scale_factor = float(self.s_num_str)
        except ValueError:
            return
        
        scale_canvas = self._get_scale()
        
        for d in self.uv_data:
            if d['point'] not in self.s_saved_pos:
                continue
            
            ox, oy = self.s_saved_pos[d['point']]
            
            vec_x = ox - self.s_center_x
            vec_y = oy - self.s_center_y
            
            if self.s_axis == 'x':
                new_vec_x = vec_x * scale_factor
                new_vec_y = vec_y
            elif self.s_axis == 'y':
                new_vec_x = vec_x
                new_vec_y = vec_y * scale_factor
            else:
                # Sin eje: escalar ambos
                new_vec_x = vec_x * scale_factor
                new_vec_y = vec_y * scale_factor
            
            new_x = self.s_center_x + new_vec_x
            new_y = self.s_center_y + new_vec_y
            
            d['vertex']['x'] = max(0, min(255, int(new_x)))
            d['vertex']['y'] = max(0, min(255, int(new_y)))
            
            self._update_point_and_lines(d, scale_canvas)
        
        self._update_faces()
        self._refresh_colors()
        self._update_coord_label()

    def _s_apply(self):
        """Confirma el S-mode"""
        self.s_mode      = False
        self.s_axis      = None
        self.s_num_str   = ""
        self.s_saved_pos = {}
        
        # Marcar como modificado y auto-guardar
        if hasattr(self, 'editor'):
            self.editor.mark_as_modified()
            self.editor.auto_save_preview()

    def _s_cancel(self):
        """Cancela S-mode restaurando posiciones"""
        scale = self._get_scale()
        for d in self.uv_data:
            if d['point'] in self.s_saved_pos:
                ox, oy = self.s_saved_pos[d['point']]
                d['vertex']['x'] = ox
                d['vertex']['y'] = oy
                self._update_point_and_lines(d, scale)
        self._update_faces()
        self._refresh_colors()
        self.s_mode      = False
        self.s_axis      = None
        self.s_num_str   = ""
        self.s_saved_pos = {}