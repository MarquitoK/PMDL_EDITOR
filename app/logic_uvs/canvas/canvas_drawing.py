from PIL import Image, ImageTk

from ..ui_components import (
    C_VERT_NORMAL, C_EDGE_NORMAL, C_FACE_SEL, FACE_STIPPLE,
    VERT_RADIUS, EDGE_WIDTH, EDGE_BORDER
)


class UVCanvasDrawing:
    """Mixin para dibujar UVs en el canvas"""
    
    # textura

    def load_texture(self, texture_path):
        try:
            self.texture_image = Image.open(texture_path)
            self.texture_base = self.texture_image.convert("RGBA").resize(
                (512, 512), Image.Resampling.NEAREST)
            self.redraw_texture()
            return True
        except Exception as e:
            print(f"Error al cargar textura: {e}")
            return False

    def redraw_texture(self):
        if not self.texture_image:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1: w = 512
        if h <= 1: h = 512

        base_size    = min(w, h)
        logical_size = max(1, int(base_size * self.zoom_level))
        render_size = min(logical_size, 4096)

        src = self.texture_base if self.texture_base else self.texture_image
        img = src.resize((render_size, render_size), Image.Resampling.NEAREST)
        self.texture_photo = ImageTk.PhotoImage(img)

        self.delete("texture")
        self.create_image(self.pan_x, self.pan_y, anchor="nw",
                          image=self.texture_photo, tags="texture")
        self.tag_lower("texture")
        self.tag_raise("mode_ui")
        self.config(scrollregion=(
            self.pan_x - w, self.pan_y - h,
            self.pan_x + logical_size + w, self.pan_y + logical_size + h
        ))

    # dibujo de UVs

    def clear_uvs(self):
        for item in self.uv_points + self.uv_lines + self.uv_faces:
            self.delete(item)
        self.delete("edge_grad")
        self.delete("uv_line_border")
        self.uv_points   = []
        self.uv_lines    = []
        self.uv_faces    = []
        self.face_items  = []
        self.face_centers = []
        self.uv_data     = []
        self.tri_data    = []
        self.selected_points = []

    def _build_subpart(self, vertices, scale):
        """Construye triángulos a partir de Triangle Strip"""
        if len(vertices) < 3:
            return

        vertex_lines = {}
        for i in range(len(vertices)):
            vertex_lines[i] = []

        for i in range(2, len(vertices)):
            if i % 2 == 0:
                a, b, c = i - 2, i - 1, i
            else:
                a, b, c = i - 1, i - 2, i

            if a < 0 or b < 0 or c < 0:
                continue
            if a >= len(vertices) or b >= len(vertices) or c >= len(vertices):
                continue

            edges = [(a, b), (b, c), (c, a)]
            for vi, vj in edges:
                exists = False
                for existing in vertex_lines.get(vi, []):
                    if existing['other_idx'] == vj:
                        exists = True
                        break
                if not exists:
                    v1_x = vertices[vi]['x'] * scale + self.pan_x
                    v1_y = vertices[vi]['y'] * scale + self.pan_y
                    v2_x = vertices[vj]['x'] * scale + self.pan_x
                    v2_y = vertices[vj]['y'] * scale + self.pan_y
                    x1, y1 = v1_x, v1_y
                    x2, y2 = v2_x, v2_y

                    border = self.create_line(
                        x1, y1, x2, y2,
                        fill="#000000", width=EDGE_BORDER,
                        tags=("uv_line_border", "uv_items")
                    )
                    line = self.create_line(
                        x1, y1, x2, y2,
                        fill=C_EDGE_NORMAL, width=EDGE_WIDTH,
                        tags=("uv_line", "uv_items")
                    )
                    self.uv_lines.append(line)
                    vertex_lines.setdefault(vi, []).append({
                        'line': line, 'border': border,
                        'is_start': True, 'other_idx': vj
                    })
                    vertex_lines.setdefault(vj, []).append({
                        'line': line, 'border': border,
                        'is_start': False, 'other_idx': vi
                    })

            tri_a_idx = len(self.uv_data) + a
            tri_b_idx = len(self.uv_data) + b
            tri_c_idx = len(self.uv_data) + c
            self.tri_data.append((tri_a_idx, tri_b_idx, tri_c_idx))

        for i, vertex in enumerate(vertices):
            x = vertex['x'] * scale + self.pan_x
            y = vertex['y'] * scale + self.pan_y
            point = self.create_oval(
                x - VERT_RADIUS, y - VERT_RADIUS,
                x + VERT_RADIUS, y + VERT_RADIUS,
                fill=C_VERT_NORMAL, outline=C_VERT_NORMAL,
                width=1, tags=("uv_point", "uv_items")
            )
            self.uv_points.append(point)
            self.uv_data.append({
                'point':         point,
                'vertex':        vertex,
                'original_x':    vertex['x'],
                'original_y':    vertex['y'],
                'lines':         vertex_lines.get(i, []),
                'vertices_list': vertices,
                'vertex_index':  i
            })

    def _build_faces(self):
        """Crea polígonos de cara y face_centers"""
        scale = self._get_scale()
        for tri in self.tri_data:
            ia, ib, ic = tri
            if (ia < len(self.uv_data) and
                    ib < len(self.uv_data) and
                    ic < len(self.uv_data)):
                da, db, dc = self.uv_data[ia], self.uv_data[ib], self.uv_data[ic]
                xa = da['vertex']['x'] * scale + self.pan_x
                ya = da['vertex']['y'] * scale + self.pan_y
                xb = db['vertex']['x'] * scale + self.pan_x
                yb = db['vertex']['y'] * scale + self.pan_y
                xc = dc['vertex']['x'] * scale + self.pan_x
                yc = dc['vertex']['y'] * scale + self.pan_y
                
                fid = self.create_polygon(
                    xa, ya, xb, yb, xc, yc,
                    fill=C_FACE_SEL, stipple=FACE_STIPPLE,
                    outline="", tags=("uv_face", "uv_items"), state='hidden'
                )
                self.uv_faces.append(fid)
                self.face_items.append(fid)
                
                cx = (xa + xb + xc) / 3
                cy = (ya + yb + yc) / 3
                center_point = self.create_oval(
                    cx - VERT_RADIUS, cy - VERT_RADIUS,
                    cx + VERT_RADIUS, cy + VERT_RADIUS,
                    fill=C_VERT_NORMAL, outline=C_VERT_NORMAL,
                    width=1, tags="face_center", state='hidden'
                )
                self.face_centers.append(center_point)
            else:
                self.face_items.append(None)
                self.face_centers.append(None)

    def draw_uvs(self, parts_data, selected_parts):
        self.delete("all")
        self.uv_points   = []
        self.uv_lines    = []
        self.uv_faces    = []
        self.face_items  = []
        self.face_centers = []
        self.uv_data     = []
        self.tri_data    = []
        self.selected_points = []

        self.redraw_texture()
        scale = self._get_scale()

        for part_idx in selected_parts:
            if part_idx >= len(parts_data):
                continue
            for subpart in parts_data[part_idx]['subparts']:
                vertices = subpart['vertices']
                if len(vertices) >= 3:
                    self._build_subpart(vertices, scale)

        self._build_faces()
        self._build_edge_map()
        for p in self.uv_points:
            self.tag_raise(p)
        
        self._create_mode_ui()

    def _reposition_all_uvs(self, old_scale, old_pan_x, old_pan_y):
        """Reposiciona todos los items UV (OPTIMIZADO HÍBRIDO)"""
        scale = self._get_scale()
        
        # Calcular cambios
        scale_changed = abs(scale - old_scale) > 0.001
        delta_x = self.pan_x - old_pan_x
        delta_y = self.pan_y - old_pan_y
        pan_changed = abs(delta_x) > 0.1 or abs(delta_y) > 0.1
        
        # OPTIMIZACIÓN
        if pan_changed and not scale_changed:
            self.move("uv_items", delta_x, delta_y)
            return
        
        # Si hay zoom, recalcular coordenadas
        for d in self.uv_data:
            sx = d['vertex']['x'] * scale + self.pan_x
            sy = d['vertex']['y'] * scale + self.pan_y
            self.coords(d['point'],
                        sx - VERT_RADIUS, sy - VERT_RADIUS,
                        sx + VERT_RADIUS, sy + VERT_RADIUS)

        # Optimizar líneas
        drawn = set()
        for d in self.uv_data:
            for li in d['lines']:
                lid = li['line']
                if lid in drawn:
                    continue
                drawn.add(lid)
                v1 = d['vertex'] if li['is_start'] else d['vertices_list'][li['other_idx']]
                v2 = d['vertices_list'][li['other_idx']] if li['is_start'] else d['vertex']
                x1 = v1['x'] * scale + self.pan_x
                y1 = v1['y'] * scale + self.pan_y
                x2 = v2['x'] * scale + self.pan_x
                y2 = v2['y'] * scale + self.pan_y
                self.coords(li['line'], x1, y1, x2, y2)
                if 'border' in li:
                    self.coords(li['border'], x1, y1, x2, y2)

        # Actualizar caras y centros
        for i, tri in enumerate(self.tri_data):
            ia, ib, ic = tri
            if ia >= len(self.uv_data) or ib >= len(self.uv_data) or ic >= len(self.uv_data):
                continue
            da, db, dc = self.uv_data[ia], self.uv_data[ib], self.uv_data[ic]
            xa = da['vertex']['x'] * scale + self.pan_x
            ya = da['vertex']['y'] * scale + self.pan_y
            xb = db['vertex']['x'] * scale + self.pan_x
            yb = db['vertex']['y'] * scale + self.pan_y
            xc = dc['vertex']['x'] * scale + self.pan_x
            yc = dc['vertex']['y'] * scale + self.pan_y
            
            fid = self.face_items[i] if i < len(self.face_items) else None
            if fid:
                self.coords(fid, xa, ya, xb, yb, xc, yc)
            
            fc = self.face_centers[i] if i < len(self.face_centers) else None
            if fc:
                cx = (xa + xb + xc) / 3
                cy = (ya + yb + yc) / 3
                self.coords(fc,
                           cx - VERT_RADIUS, cy - VERT_RADIUS,
                           cx + VERT_RADIUS, cy + VERT_RADIUS)

    def _update_point_and_lines(self, data, scale=None):
        """Reposiciona óvalo y edges durante G-mode"""
        if scale is None:
            scale = self._get_scale()
        sx = data['vertex']['x'] * scale + self.pan_x
        sy = data['vertex']['y'] * scale + self.pan_y
        self.coords(data['point'],
                    sx - VERT_RADIUS, sy - VERT_RADIUS,
                    sx + VERT_RADIUS, sy + VERT_RADIUS)
        for li in data['lines']:
            ov = data['vertices_list'][li['other_idx']]
            ox = ov['x'] * scale + self.pan_x
            oy = ov['y'] * scale + self.pan_y
            if li['is_start']:
                new_coords = (sx, sy, ox, oy)
            else:
                new_coords = (ox, oy, sx, sy)
            self.coords(li['line'],   *new_coords)
            if 'border' in li:
                self.coords(li['border'], *new_coords)

    def _update_faces(self):
        """Actualiza polígonos de cara y face_centers"""
        sel_set = set(self.selected_points)
        scale   = self._get_scale()
        for i, tri in enumerate(self.tri_data):
            ia, ib, ic = tri
            if (ia >= len(self.uv_data) or
                    ib >= len(self.uv_data) or
                    ic >= len(self.uv_data)):
                continue
            da, db, dc = self.uv_data[ia], self.uv_data[ib], self.uv_data[ic]
            all_sel = (da['point'] in sel_set and
                       db['point'] in sel_set and
                       dc['point'] in sel_set)
            
            xa = da['vertex']['x'] * scale + self.pan_x
            ya = da['vertex']['y'] * scale + self.pan_y
            xb = db['vertex']['x'] * scale + self.pan_x
            yb = db['vertex']['y'] * scale + self.pan_y
            xc = dc['vertex']['x'] * scale + self.pan_x
            yc = dc['vertex']['y'] * scale + self.pan_y
            
            fid = self.face_items[i] if i < len(self.face_items) else None
            if fid:
                self.coords(fid, xa, ya, xb, yb, xc, yc)
                self.itemconfig(fid, state='normal' if all_sel else 'hidden')
            
            fc = self.face_centers[i] if i < len(self.face_centers) else None
            if fc:
                cx = (xa + xb + xc) / 3
                cy = (ya + yb + yc) / 3
                self.coords(fc,
                           cx - VERT_RADIUS, cy - VERT_RADIUS,
                           cx + VERT_RADIUS, cy + VERT_RADIUS)