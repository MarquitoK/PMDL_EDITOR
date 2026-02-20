from ..ui_components import (
    C_VERT_NORMAL, C_VERT_SEL, C_EDGE_NORMAL, C_EDGE_SEL, C_EDGE_HALF,
    EDGE_WIDTH, EDGE_BORDER
)
from ..selection_modes import find_island_vertices


class UVCanvasSelection:
    
    def _create_mode_ui(self):
        self.mode_buttons = []
        pass

    def _set_selection_mode(self, mode):
        """Cambia el modo de selección y actualiza la UI."""
        self.selection_mode = mode
        
        # Actualizar botones del header si existen
        if hasattr(self, 'editor') and hasattr(self.editor, 'set_uv_selection_mode'):
            self.editor.set_uv_selection_mode(mode)
        else:
            print(f"WARNING: No se pudo actualizar botones del header (editor={hasattr(self, 'editor')})")
        
        self._update_visibility_by_mode()
        self._deselect_all()

    def _update_visibility_by_mode(self):
        """Muestra/oculta elementos según el modo"""
        if self.selection_mode == 'vertex' or self.selection_mode == 'island':
            for p in self.uv_points:
                self.itemconfig(p, state='normal')
            for fc in self.face_centers:
                if fc:
                    self.itemconfig(fc, state='hidden')
        
        elif self.selection_mode == 'face':
            for p in self.uv_points:
                self.itemconfig(p, state='hidden')
            for fc in self.face_centers:
                if fc:
                    self.itemconfig(fc, state='normal')

    def _update_coord_label(self):
        """Actualiza el label de coordenadas"""
        if not self.coord_label:
            return
        if not self.selected_points:
            self.coord_label.configure(text="By - Los ijue30s")
            return
        last_point = self.selected_points[-1]
        for d in self.uv_data:
            if d['point'] == last_point:
                x = d['vertex']['x']
                y = d['vertex']['y']
                self.coord_label.configure(text=f"X: {x}  Y: {y}")
                return

    def _build_edge_map(self):
        """Cachea el edge_map"""
        self._edge_map = {}
        for d in self.uv_data:
            for li in d['lines']:
                lid = li['line']
                if lid not in self._edge_map:
                    self._edge_map[lid] = [None, None]
                if li['is_start']:
                    self._edge_map[lid][0] = d
                else:
                    self._edge_map[lid][1] = d

    def _refresh_colors(self):
        """Actualiza colores según selección y modo"""
        sel_set = set(self.selected_points)

        for d in self.uv_data:
            col = C_VERT_SEL if d['point'] in sel_set else C_VERT_NORMAL
            self.itemconfig(d['point'], fill=col, outline=col)

        self.delete("edge_grad")

        edge_map = getattr(self, '_edge_map', {})
        
        # Degradados normales para todos los modos
        for lid, (ds, de) in edge_map.items():
            if ds is None or de is None:
                continue
            s_sel = ds['point'] in sel_set
            e_sel = de['point'] in sel_set
            if s_sel and e_sel:
                self.itemconfig(lid, fill=C_EDGE_SEL)
            elif s_sel or e_sel:
                coords = self.coords(lid)
                if len(coords) == 4:
                    x1, y1, x2, y2 = coords
                    ox, oy, fx, fy = (x1, y1, x2, y2) if s_sel else (x2, y2, x1, y1)
                    mx1, my1 = ox + (fx - ox) * 0.33, oy + (fy - oy) * 0.33
                    mx2, my2 = ox + (fx - ox) * 0.66, oy + (fy - oy) * 0.66
                    self.itemconfig(lid, fill=C_EDGE_NORMAL)
                    self.create_line(ox, oy, fx, fy, fill="#000000", width=EDGE_BORDER, tags=("edge_grad", "uv_items"))
                    self.create_line(ox, oy, mx1, my1, fill=C_EDGE_SEL, width=EDGE_WIDTH, tags=("edge_grad", "uv_items"))
                    self.create_line(mx1, my1, mx2, my2, fill=C_EDGE_HALF, width=EDGE_WIDTH, tags=("edge_grad", "uv_items"))
                    self.create_line(mx2, my2, fx, fy, fill=C_EDGE_NORMAL, width=EDGE_WIDTH, tags=("edge_grad", "uv_items"))
            else:
                self.itemconfig(lid, fill=C_EDGE_NORMAL)

        # Caras
        for i, tri in enumerate(self.tri_data):
            ia, ib, ic = tri
            if ia >= len(self.uv_data) or ib >= len(self.uv_data) or ic >= len(self.uv_data):
                continue
            all_sel = (self.uv_data[ia]['point'] in sel_set and
                       self.uv_data[ib]['point'] in sel_set and
                       self.uv_data[ic]['point'] in sel_set)
            fid = self.face_items[i] if i < len(self.face_items) else None
            if fid:
                self.itemconfig(fid, state='normal' if all_sel else 'hidden')

        for i, fc in enumerate(self.face_centers):
            if not fc:
                continue
            if i < len(self.tri_data):
                ia, ib, ic = self.tri_data[i]
                if ia < len(self.uv_data) and ib < len(self.uv_data) and ic < len(self.uv_data):
                    all_sel = (self.uv_data[ia]['point'] in sel_set and
                              self.uv_data[ib]['point'] in sel_set and
                              self.uv_data[ic]['point'] in sel_set)
                    col = C_VERT_SEL if all_sel else C_VERT_NORMAL
                    self.itemconfig(fc, fill=col, outline=col)

        self.tag_raise("uv_point")

    def _deselect_all(self):
        self.selected_points.clear()
        self.delete("edge_grad")
        self._refresh_colors()
        self._update_coord_label()

    def _select_point(self, canvas_id, add=False):
        self.delete("edge_grad")
        if not add:
            self.selected_points.clear()
        if canvas_id not in self.selected_points:
            self.selected_points.append(canvas_id)
        self._refresh_colors()
        self._update_coord_label()

    def _select_all_points(self):
        self.delete("edge_grad")
        self.selected_points = [d['point'] for d in self.uv_data]
        self._refresh_colors()
        self._update_coord_label()

    def _select_face_by_center(self, center_id, add=False):
        """Selecciona cara por su punto central"""
        if not add:
            self.selected_points.clear()
        for i, fc in enumerate(self.face_centers):
            if fc == center_id and i < len(self.tri_data):
                ia, ib, ic = self.tri_data[i]
                if ia < len(self.uv_data) and ib < len(self.uv_data) and ic < len(self.uv_data):
                    for idx in [ia, ib, ic]:
                        pt = self.uv_data[idx]['point']
                        if pt not in self.selected_points:
                            self.selected_points.append(pt)
                break
        self._refresh_colors()
        self._update_coord_label()

    def _select_island_by_vertex(self, point_id, add=False):
        """Selecciona isla completa"""
        if not add:
            self.selected_points.clear()
        start_idx = None
        for idx, d in enumerate(self.uv_data):
            if d['point'] == point_id:
                start_idx = idx
                break
        if start_idx is None:
            return
        
        island = find_island_vertices(start_idx, self.uv_data)
        
        for idx in island:
            pt = self.uv_data[idx]['point']
            if pt not in self.selected_points:
                self.selected_points.append(pt)
        self._refresh_colors()
        self._update_coord_label()

    def _select_island_under_cursor(self):
        """Selecciona isla bajo el cursor (tecla L)"""
        items = self.find_overlapping(
            self._mouse_x - 6, self._mouse_y - 6,
            self._mouse_x + 6, self._mouse_y + 6)
        point_found = None
        for item in items:
            if "uv_point" in self.gettags(item):
                point_found = item
                break
        if not point_found:
            return
        
        start_idx = None
        for idx, d in enumerate(self.uv_data):
            if d['point'] == point_found:
                start_idx = idx
                break
        if start_idx is None:
            return
        
        island = find_island_vertices(start_idx, self.uv_data)
        
        self.selected_points = [self.uv_data[idx]['point'] for idx in island]
        self._refresh_colors()
        self._update_coord_label()