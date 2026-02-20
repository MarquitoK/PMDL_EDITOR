class UVCanvasEvents:
    """Mixin para eventos de mouse y teclado"""
    
    def _setup_bindings(self):
        """Configura todos los bindings de eventos"""
        self.bind("<ButtonPress-1>",   self.on_left_press)
        self.bind("<B1-Motion>",       self.on_box_select_drag)
        self.bind("<ButtonRelease-1>", self.on_left_release)
        self.bind("<ButtonPress-3>",   self.on_right_press)
        self.bind("<MouseWheel>",      self.on_zoom)
        self.bind("<Button-2>",        self.on_pan_start)
        self.bind("<B2-Motion>",       self.on_pan_drag)
        self.bind("<ButtonRelease-2>", self.on_pan_release)
        self.bind("<Motion>",          self.on_mouse_move)
        self.bind("<KeyPress>",        self.on_key_press)
        self.bind("<ButtonPress-1>",   self._grab_focus, add=True)

    # eventos de mouse

    def on_left_press(self, event):
        if self.g_mode:
            self._g_apply()
            return
        
        if self.s_mode:
            self._s_apply()
            return

        # Convertir coordenadas de evento a coordenadas del canvas
        canvas_x = self.canvasx(event.x)
        canvas_y = self.canvasy(event.y)

        shift = bool(event.state & 0x1)
        items = self.find_overlapping(
            canvas_x - 6, canvas_y - 6, canvas_x + 6, canvas_y + 6)

        if self.selection_mode == 'vertex':
            point_found = False
            for item in items:
                if "uv_point" in self.gettags(item):
                    self._select_point(item, add=shift)
                    point_found = True
                    break
            if not point_found:
                self._start_box_select(event)
        
        elif self.selection_mode == 'face':
            face_found = False
            for item in items:
                if "face_center" in self.gettags(item):
                    self._select_face_by_center(item, add=shift)
                    face_found = True
                    break
            if not face_found:
                self._start_box_select(event)
        
        elif self.selection_mode == 'island':
            point_found = False
            for item in items:
                if "uv_point" in self.gettags(item):
                    self._select_island_by_vertex(item, add=shift)
                    point_found = True
                    break
            if not point_found:
                self._start_box_select(event)

    def _start_box_select(self, event):
        """Inicia la selección por caja"""
        self._deselect_all()
        self.is_selecting      = True
        # Usar coordenadas del canvas
        self.selection_start_x = self.canvasx(event.x)
        self.selection_start_y = self.canvasy(event.y)
        if self.selection_rect:
            self.delete(self.selection_rect)
        self.selection_rect = self.create_rectangle(
            self.selection_start_x, self.selection_start_y, 
            self.selection_start_x, self.selection_start_y,
            outline="#FFFFFF", dash=(4, 4), width=1, tags="selection"
        )

    def on_box_select_drag(self, event):
        if self.is_selecting and self.selection_rect:
            # Usar coordenadas del canvas
            canvas_x = self.canvasx(event.x)
            canvas_y = self.canvasy(event.y)
            self.coords(self.selection_rect,
                        self.selection_start_x, self.selection_start_y,
                        canvas_x, canvas_y)

    def on_left_release(self, event):
        if not self.is_selecting:
            return
        self.is_selecting = False
        if not self.selection_rect:
            return
        coords = self.coords(self.selection_rect)
        self.delete(self.selection_rect)
        self.selection_rect = None
        if len(coords) < 4:
            return
        x1, y1, x2, y2 = coords
        mn_x, mx_x = min(x1, x2), max(x1, x2)
        mn_y, mx_y = min(y1, y2), max(y1, y2)
        if mx_x - mn_x <= 2 and mx_y - mn_y <= 2:
            return
        self.delete("edge_grad")
        
        if self.selection_mode == 'vertex' or self.selection_mode == 'island':
            for point in self.uv_points:
                pc = self.coords(point)
                if not pc:
                    continue
                cx = (pc[0] + pc[2]) / 2
                cy = (pc[1] + pc[3]) / 2
                if mn_x <= cx <= mx_x and mn_y <= cy <= mx_y:
                    if point not in self.selected_points:
                        self.selected_points.append(point)
        
        elif self.selection_mode == 'face':
            for fc in self.face_centers:
                if not fc:
                    continue
                fc_coords = self.coords(fc)
                if not fc_coords:
                    continue
                cx = (fc_coords[0] + fc_coords[2]) / 2
                cy = (fc_coords[1] + fc_coords[3]) / 2
                if mn_x <= cx <= mx_x and mn_y <= cy <= mx_y:
                    self._select_face_by_center(fc, add=True)
        
        self._refresh_colors()
        self._update_coord_label()

    def on_right_press(self, event):
        if self.g_mode:
            self._g_cancel()
        if self.s_mode:
            self._s_cancel()

    def on_mouse_move(self, event):
        """Trackea posición del mouse"""
        # Usar coordenadas del canvas
        self._mouse_x = self.canvasx(event.x)
        self._mouse_y = self.canvasy(event.y)
        if self.g_mode and not self.g_num_str:
            self._g_move_free(self._mouse_x, self._mouse_y)
        if self.s_mode and not self.s_num_str:
            self._s_move_free(self._mouse_x, self._mouse_y)

    # teclado

    def on_key_press(self, event):
        key  = event.keysym.lower()
        char = event.char
        ctrl = bool(event.state & 0x4)

        # Ctrl+Z: Undo
        if ctrl and key == 'z':
            self._undo()
            return

        # Ctrl+Y: Redo
        if ctrl and key == 'y':
            self._redo()
            return

        # Activar G-mode
        if key == 'g' and not self.g_mode and not self.s_mode:
            self._g_start()
            return

        # Activar S-mode
        if key == 's' and not self.s_mode and not self.g_mode:
            self._s_start()
            return

        # Dentro de G-mode
        if self.g_mode:
            if key == 'x' and not self.g_num_str:
                self.g_axis = 'x'
                scale = self._get_scale()
                for d in self.uv_data:
                    if d['point'] in self.g_saved_pos:
                        _, oy = self.g_saved_pos[d['point']]
                        d['vertex']['y'] = oy
                        self._update_point_and_lines(d, scale)
                self._update_faces()
                self._g_move_free(self._mouse_x, self._mouse_y)
                return
            if key == 'y' and not self.g_num_str:
                self.g_axis = 'y'
                scale = self._get_scale()
                for d in self.uv_data:
                    if d['point'] in self.g_saved_pos:
                        ox, _ = self.g_saved_pos[d['point']]
                        d['vertex']['x'] = ox
                        self._update_point_and_lines(d, scale)
                self._update_faces()
                self._g_move_free(self._mouse_x, self._mouse_y)
                return
            if self.g_axis is not None:
                if char.isdigit():
                    self.g_num_str += char
                    self._g_apply_numeric()
                    return
                if key == 'backspace':
                    self.g_num_str = self.g_num_str[:-1]
                    if self.g_num_str:
                        self._g_apply_numeric()
                    else:
                        self._g_move_free(self._mouse_x, self._mouse_y)
                    return
            if key == 'return':
                self._g_apply()
                return
            if key == 'escape':
                self._g_cancel()
                return
            return

        # Dentro de S-mode
        if self.s_mode:
            if key == 'x' and not self.s_num_str:
                self.s_axis = 'x'
                self._s_move_free(self._mouse_x, self._mouse_y)
                return
            if key == 'y' and not self.s_num_str:
                self.s_axis = 'y'
                self._s_move_free(self._mouse_x, self._mouse_y)
                return
            if self.s_axis is not None or True:
                if char.isdigit() or char == '.' or char == '-':
                    self.s_num_str += char
                    self._s_apply_numeric()
                    return
                if key == 'backspace':
                    self.s_num_str = self.s_num_str[:-1]
                    if self.s_num_str:
                        self._s_apply_numeric()
                    else:
                        self._s_move_free(self._mouse_x, self._mouse_y)
                    return
            if key == 'return':
                self._s_apply()
                return
            if key == 'escape':
                self._s_cancel()
                return
            return

        if key == 'a':
            if len(self.selected_points) == len(self.uv_points):
                self._deselect_all()
            else:
                self._select_all_points()
            return

        if key == '1':
            self._set_selection_mode('vertex')
            return
        if key == '2':
            self._set_selection_mode('island')
            return
        if key == '3':
            self._set_selection_mode('face')
            return

        if key == 'l':
            self._select_island_under_cursor()
            return

        if key == 'escape':
            self._deselect_all()