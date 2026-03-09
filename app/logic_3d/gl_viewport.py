import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

try:
    from pyopengltk import OpenGLFrame
    
    class GLViewport(OpenGLFrame):
        def __init__(self, parent, **kwargs):
            super().__init__(parent, **kwargs)
            
            self.rotation_x = 0
            self.rotation_y = 180
            self.zoom = 10.0
            self.pan_x = 0
            self.pan_y = -0.8
            
            # Centro de rotación (punto pivote)
            self.pivot_x = 0
            self.pivot_y = 0
            self.pivot_z = 0
            
            self.last_x = 0
            self.last_y = 0
            self.dragging = False
            self.drag_button = None
            
            self.mesh_data = None
            self.render_mode = "texture"
            self.texture_id = None
            self.selected_parts = set()
            self.viewing_mode = 'all'
            self.current_part_index = -1
            
            self.bones_data = []
            self.bones_visible = True
            self.selected_bone = None
            self.bones_names = {}
            
            # Matrices GL cacheadas al final de cada redraw para raycast preciso
            self._gl_modelview  = None
            self._gl_projection = None
            self._gl_viewport   = None
            
            self.solid_colors_cache = None
            
            # Bindings de mouse
            self.bind("<ButtonPress-1>", self.on_mouse_down)
            self.bind("<ButtonPress-2>", self.on_mouse_down)
            self.bind("<ButtonPress-3>", self.on_mouse_down)
            self.bind("<ButtonRelease-1>", self.on_mouse_up)
            self.bind("<ButtonRelease-2>", self.on_mouse_up)
            self.bind("<ButtonRelease-3>", self.on_mouse_up)
            self.bind("<Motion>", self.on_mouse_move)
            self.bind("<MouseWheel>", self.on_mouse_wheel)
            self.bind("<Key>", self.on_key_press)
            
            # Hacer el widget focusable para detectar teclas
            self.focus_set()
            
            # Referencia al label de información
            self.info_label = None
            # Referencia a la app principal
            self.parent_app = None

            self.animate = 1

            self.after(100, self._initial_camera_nudge)

        def _initial_camera_nudge(self):
            try:
                self.rotation_y = 180.1
                self.redraw()
                self.after(50, lambda: setattr(self, 'rotation_y', 180) or self.redraw())
            except Exception:
                self.after(100, self._initial_camera_nudge)

        def initgl(self):
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

            glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
            glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.3, 0.3, 0.3, 1])
            glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.8, 0.8, 0.8, 1])

            glClearColor(0.15, 0.15, 0.18, 1.0)
            glShadeModel(GL_SMOOTH)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            self._grid_vbo   = None
            self._grid_count = 0
            self._axes_vbo   = None
            self._axes_count = 0
            self._build_grid_vbos()

        def trigger_mini_rotation(self):
            self.rotation_y += 0.01
            if self.rotation_y > 360:
                self.rotation_y -= 360
            self.redraw()

        def _render_loop(self):
            pass

        def redraw(self):
            self._do_redraw()

        def _do_redraw(self):
            try:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                width  = self.winfo_width()
                height = max(self.winfo_height(), 1)
                gluPerspective(45, width / height, 0.1, 100.0)

                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                glTranslatef(self.pan_x, self.pan_y, -self.zoom)
                glRotatef(self.rotation_x, 1, 0, 0)
                glRotatef(self.rotation_y, 0, 1, 0)
                glTranslatef(-self.pivot_x, -self.pivot_y, -self.pivot_z)

                if self.mesh_data:
                    self.draw_grid()
                    self.draw_mesh()

                if self.bones_visible and self.bones_data:
                    self.draw_bones()

                try:
                    self._gl_modelview  = glGetDoublev(GL_MODELVIEW_MATRIX)
                    self._gl_projection = glGetDoublev(GL_PROJECTION_MATRIX)
                    self._gl_viewport   = glGetIntegerv(GL_VIEWPORT)
                except Exception:
                    pass

                glFlush()
                try:
                    self.tkSwapBuffers()
                except Exception:
                    pass
            except Exception:
                pass
        
        def _build_grid_vbos(self):
            """Construye los VBOs del grid y ejes una sola vez."""
            size = 2.0
            step = 0.2
            pts = []
            for i in np.arange(-size, size + step * 0.5, step):
                i = round(float(i), 6)
                pts += [i, 0, -size,  i, 0,  size]
                pts += [-size, 0, i,   size, 0, i]
            grid_arr = np.array(pts, dtype=np.float32)
            self._grid_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._grid_vbo)
            glBufferData(GL_ARRAY_BUFFER, grid_arr.nbytes, grid_arr, GL_STATIC_DRAW)
            self._grid_count = len(grid_arr) // 3

            axes_arr = np.array([
                0,0,0,  0.5,0,0,
                0,0,0,  0,0.5,0,
                0,0,0,  0,0,0.5,
            ], dtype=np.float32)
            self._axes_vbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._axes_vbo)
            glBufferData(GL_ARRAY_BUFFER, axes_arr.nbytes, axes_arr, GL_STATIC_DRAW)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

        def draw_grid(self):
            glDisable(GL_LIGHTING)
            glEnableClientState(GL_VERTEX_ARRAY)

            # Grid
            glColor3f(0.25, 0.25, 0.28)
            glBindBuffer(GL_ARRAY_BUFFER, self._grid_vbo)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glDrawArrays(GL_LINES, 0, self._grid_count)

            # Ejes (coloreados por segmento con 2 vértices cada uno)
            glLineWidth(3.0)
            glBindBuffer(GL_ARRAY_BUFFER, self._axes_vbo)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glColor3f(1, 0.2, 0.2);  glDrawArrays(GL_LINES, 0, 2)
            glColor3f(0.2, 1, 0.2);  glDrawArrays(GL_LINES, 2, 2)
            glColor3f(0.3, 0.5, 1);  glDrawArrays(GL_LINES, 4, 2)
            glLineWidth(1.0)

            glDisableClientState(GL_VERTEX_ARRAY)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glEnable(GL_LIGHTING)
        
        def draw_mesh(self):
            if self.render_mode == "wireframe":
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                glDisable(GL_LIGHTING)
                glDisable(GL_TEXTURE_2D)
                glLineWidth(1.5)
            else:
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                glDisable(GL_LIGHTING)
                if self.render_mode == "texture" and self.texture_id is not None:
                    glEnable(GL_TEXTURE_2D)
                    glBindTexture(GL_TEXTURE_2D, self.texture_id)
                    glColor3f(1.0, 1.0, 1.0)
                else:
                    glDisable(GL_TEXTURE_2D)

            glEnableClientState(GL_VERTEX_ARRAY)

            for parte_data in self.mesh_data:
                vbo_v   = parte_data.get('vbo_vertices')
                vbo_uv  = parte_data.get('vbo_uvs')
                vbo_idx = parte_data.get('vbo_indices')
                vbo_sv  = parte_data.get('vbo_solid_vertices')
                vbo_sc  = parte_data.get('vbo_solid_colors')
                n_idx   = parte_data.get('n_indices', 0)
                n_solid = parte_data.get('n_solid', 0)
                opacidad = parte_data.get('opacidad', 1.0)

                if self.render_mode == "solid":
                    if vbo_sv is None or n_solid == 0:
                        continue
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_sv)
                    glVertexPointer(3, GL_FLOAT, 0, None)
                    glEnableClientState(GL_COLOR_ARRAY)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_sc)
                    glColorPointer(4, GL_FLOAT, 0, None)
                    glDrawArrays(GL_TRIANGLES, 0, n_solid)
                    glDisableClientState(GL_COLOR_ARRAY)
                else:
                    if vbo_v is None or n_idx == 0:
                        continue
                    color = parte_data['color']
                    if self.render_mode == "texture":
                        if self.texture_id is None:
                            glColor4f(color[0], color[1], color[2], opacidad)
                        else:
                            glColor4f(1.0, 1.0, 1.0, opacidad)
                        if self.texture_id is not None and vbo_uv is not None:
                            glEnableClientState(GL_TEXTURE_COORD_ARRAY)
                            glBindBuffer(GL_ARRAY_BUFFER, vbo_uv)
                            glTexCoordPointer(2, GL_FLOAT, 0, None)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_v)
                    glVertexPointer(3, GL_FLOAT, 0, None)
                    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, vbo_idx)
                    glDrawElements(GL_TRIANGLES, n_idx, GL_UNSIGNED_INT, None)
                    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
                    if self.render_mode == "texture" and self.texture_id is not None and vbo_uv is not None:
                        glDisableClientState(GL_TEXTURE_COORD_ARRAY)

            glDisableClientState(GL_VERTEX_ARRAY)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

            if self.render_mode == "wireframe":
                glLineWidth(1.0)
            glDisable(GL_TEXTURE_2D)

            self.draw_selection_outline()
            self.draw_selection_info()

        def draw_selection_outline(self):
            if not self.selected_parts or not self.mesh_data:
                return

            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_DEPTH_TEST)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glLineWidth(4.0)
            glColor3f(1.0, 1.0, 0.0)
            glEnableClientState(GL_VERTEX_ARRAY)

            for idx in self.selected_parts:
                if idx < len(self.mesh_data):
                    parte_data = self.mesh_data[idx]
                    vbo_v  = parte_data.get('vbo_vertices')
                    vbo_idx = parte_data.get('vbo_indices')
                    n_idx  = parte_data.get('n_indices', 0)
                    if vbo_v is None or n_idx == 0:
                        continue
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_v)
                    glVertexPointer(3, GL_FLOAT, 0, None)
                    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, vbo_idx)
                    glDrawElements(GL_TRIANGLES, n_idx, GL_UNSIGNED_INT, None)
                    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

            glDisableClientState(GL_VERTEX_ARRAY)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glLineWidth(1.0)
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)

        
        def _write_info(self, segments):
            import tkinter as tk
            if not self.info_label or not isinstance(self.info_label, tk.Text):
                return
            self.info_label.configure(state="normal")
            self.info_label.delete("1.0", "end")
            if not segments:
                self.info_label.place_forget()
                self.info_label.configure(state="disabled")
                return
            for text, tag in segments:
                self.info_label.insert("end", text, tag)
            self.info_label.configure(state="disabled")
            # Ajustar alto al número de líneas reales
            content_text = "".join(t for t, _ in segments)
            lines = content_text.count("\n") + 1
            max_line_len = max((len(l) for l in content_text.split("\n")), default=10)
            self.info_label.configure(height=lines, width=max(18, max_line_len + 2))
            self.info_label.place(relx=1.0, rely=0.0, x=-30, y=30, anchor="ne")

        def draw_selection_info(self):
            """Actualiza la información de la parte/subparte seleccionada en el label"""
            if not self.info_label:
                return

            if self.selected_bone is not None:
                return

            if not self.selected_parts or not self.mesh_data:
                self._write_info([])
                if self.viewing_mode == 'all' and self.parent_app and hasattr(self.parent_app, 'parte_buttons'):
                    for idx, btn in self.parent_app.parte_buttons.items():
                        if idx == -1:
                            btn.configure(fg_color=("#3B8ED0", "#1F6AA5"))
                        else:
                            btn.configure(fg_color=("gray75", "gray20"))
                return

            if self.viewing_mode == 'all':
                first_idx = list(self.selected_parts)[0]
                if first_idx < len(self.mesh_data):
                    part_index = self.mesh_data[first_idx].get('part_index', first_idx)

                    if self.parent_app and hasattr(self.parent_app, 'parte_buttons'):
                        for idx, btn in self.parent_app.parte_buttons.items():
                            if idx == -1:
                                btn.configure(fg_color=("#3B8ED0", "#1F6AA5"))
                            elif idx == part_index:
                                btn.configure(fg_color=("#FFD700", "#DAA520"))
                            else:
                                btn.configure(fg_color=("gray75", "gray20"))

                    total_vertices = 0
                    total_triangulos = 0
                    total_edges = set()
                    num_subpartes = 0

                    for idx in self.selected_parts:
                        if idx < len(self.mesh_data):
                            md = self.mesh_data[idx]
                            total_vertices += len(md['vertices'])
                            total_triangulos += len(md['triangulos'])
                            num_subpartes += 1
                            for tri in md['triangulos']:
                                total_edges.add(tuple(sorted([tri[0], tri[1]])))
                                total_edges.add(tuple(sorted([tri[1], tri[2]])))
                                total_edges.add(tuple(sorted([tri[2], tri[0]])))

                    segs = [
                        (f"Parte_{part_index:02d}", "bold_yellow"), ("\n", "normal_white"),
                        ("Vértices:", "bold_white"), (f" {total_vertices}\n", "normal_white"),
                        ("Caras:", "bold_white"), (f" {total_triangulos}\n", "normal_white"),
                        ("Aristas:", "bold_white"), (f" {len(total_edges)}\n", "normal_white"),
                        ("SubPartes:", "bold_white"), (f" {num_subpartes}", "normal_white"),
                    ]
                    self._write_info(segs)
            else:
                if len(self.selected_parts) == 1:
                    idx = list(self.selected_parts)[0]
                    if idx < len(self.mesh_data):
                        parte_data = self.mesh_data[idx]
                        num_vertices = len(parte_data['vertices'])
                        num_triangulos = len(parte_data['triangulos'])
                        edges = set()
                        for tri in parte_data['triangulos']:
                            edges.add(tuple(sorted([tri[0], tri[1]])))
                            edges.add(tuple(sorted([tri[1], tri[2]])))
                            edges.add(tuple(sorted([tri[2], tri[0]])))
                        num_edges = len(edges)

                        segs = [
                            (f"SubParte {idx:02d}/{len(self.mesh_data):02d}", "bold_yellow"), ("\n", "normal_white"),
                            ("Vértices:", "bold_white"), (f" {num_vertices}\n", "normal_white"),
                            ("Caras:", "bold_white"), (f" {num_triangulos}\n", "normal_white"),
                            ("Aristas:", "bold_white"), (f" {num_edges}", "normal_white"),
                        ]
                        self._write_info(segs)
                else:
                    self._write_info([])
        
        def handle_selection(self, mouse_x, mouse_y, shift_pressed):
            """Maneja la selección de partes/subpartes con raycast 3D"""
            if not self.mesh_data:
                return
            ray_origin, ray_direction = self.mouse_to_ray(mouse_x, mouse_y)
            if ray_origin is None:
                return
            closest_index = None
            closest_distance = float('inf')
            hits = 0
            for idx, parte_data in enumerate(self.mesh_data):
                vertices = parte_data['vertices']
                triangulos = parte_data['triangulos']
                for tri in triangulos:
                    if all(i < len(vertices) for i in tri):
                        v0 = vertices[tri[0]]
                        v1 = vertices[tri[1]]
                        v2 = vertices[tri[2]]
                        hit, distance = self.ray_triangle_intersection(ray_origin, ray_direction, v0, v1, v2)
                        if hit:
                            hits += 1
                            if distance < closest_distance:
                                closest_distance = distance
                                if self.viewing_mode == 'all' and 'part_index' in parte_data:
                                    closest_index = parte_data['part_index']
                                else:
                                    closest_index = idx
            if self.viewing_mode == 'all' and closest_index is not None:
                indices_to_select = set()
                for idx, parte_data in enumerate(self.mesh_data):
                    if parte_data.get('part_index') == closest_index:
                        indices_to_select.add(idx)
                if shift_pressed:
                    if indices_to_select.issubset(self.selected_parts):
                        self.selected_parts -= indices_to_select
                    else:
                        self.selected_parts.update(indices_to_select)
                else:
                    self.selected_parts = indices_to_select
                
                # Actualizar parte seleccionada en parent_app y cargar UVs
                if self.parent_app and not shift_pressed:
                    self.parent_app.parte_seleccionada = closest_index
                    if hasattr(self.parent_app, 'uv_panel_visible') and self.parent_app.uv_panel_visible:
                        if hasattr(self.parent_app, 'load_uvs_for_selected_part'):
                            self.parent_app.load_uvs_for_selected_part()
            elif self.viewing_mode == 'single' and closest_index is not None:
                if shift_pressed:
                    if closest_index in self.selected_parts:
                        self.selected_parts.remove(closest_index)
                    else:
                        self.selected_parts.add(closest_index)
                else:
                    self.selected_parts = {closest_index}
            else:
                if not shift_pressed:
                    self.selected_parts.clear()
            
            self.selected_bone = None
            self.redraw()
        
        def get_view_matrix(self):
            """Obtiene la matriz de vista actual como numpy array"""
            mat = np.eye(4, dtype=np.float32)
            translate1 = np.eye(4, dtype=np.float32)
            translate1[0, 3] = self.pan_x
            translate1[1, 3] = self.pan_y
            translate1[2, 3] = -self.zoom
            angle_x_rad = np.radians(self.rotation_x)
            cos_x = np.cos(angle_x_rad)
            sin_x = np.sin(angle_x_rad)
            rot_x = np.array([[1, 0, 0, 0], [0, cos_x, -sin_x, 0], [0, sin_x, cos_x, 0], [0, 0, 0, 1]], dtype=np.float32)
            angle_y_rad = np.radians(self.rotation_y)
            cos_y = np.cos(angle_y_rad)
            sin_y = np.sin(angle_y_rad)
            rot_y = np.array([[cos_y, 0, sin_y, 0], [0, 1, 0, 0], [-sin_y, 0, cos_y, 0], [0, 0, 0, 1]], dtype=np.float32)
            translate2 = np.eye(4, dtype=np.float32)
            translate2[0, 3] = -self.pivot_x
            translate2[1, 3] = -self.pivot_y
            translate2[2, 3] = -self.pivot_z
            mat = translate1 @ rot_x @ rot_y @ translate2
            return mat
        
        def get_projection_matrix(self):
            """Obtiene la matriz de proyección actual"""
            width = self.winfo_width()
            height = self.winfo_height()
            if height == 0:
                height = 1
            aspect = width / height
            fov_rad = np.radians(45)
            near = 0.1
            far = 100.0
            f = 1.0 / np.tan(fov_rad / 2.0)
            proj = np.zeros((4, 4), dtype=np.float32)
            proj[0, 0] = f / aspect
            proj[1, 1] = f
            proj[2, 2] = (far + near) / (near - far)
            proj[2, 3] = (2.0 * far * near) / (near - far)
            proj[3, 2] = -1.0
            return proj
        
        def mouse_to_ray(self, mouse_x, mouse_y):
            """Convierte coordenadas de mouse a un ray 3D usando matrices inversas"""
            try:
                width = self.winfo_width()
                height = self.winfo_height()
                if width == 0 or height == 0:
                    return None, None
                x_ndc = (2.0 * mouse_x) / width - 1.0
                y_ndc = 1.0 - (2.0 * mouse_y) / height
                proj_matrix = self.get_projection_matrix()
                view_matrix = self.get_view_matrix()
                vp_matrix = proj_matrix @ view_matrix
                try:
                    vp_inv = np.linalg.inv(vp_matrix)
                except np.linalg.LinAlgError:
                    print("Error: Matriz singular, no se puede invertir")
                    return None, None
                near_point_ndc = np.array([x_ndc, y_ndc, -1.0, 1.0])
                far_point_ndc = np.array([x_ndc, y_ndc, 1.0, 1.0])
                near_point_world = vp_inv @ near_point_ndc
                far_point_world = vp_inv @ far_point_ndc
                if near_point_world[3] != 0:
                    near_point_world /= near_point_world[3]
                if far_point_world[3] != 0:
                    far_point_world /= far_point_world[3]
                ray_origin = near_point_world[:3]
                ray_direction = far_point_world[:3] - near_point_world[:3]
                ray_direction = ray_direction / np.linalg.norm(ray_direction)
                return ray_origin, ray_direction
            except Exception as e:
                print(f"Error en mouse_to_ray: {e}")
                import traceback
                traceback.print_exc()
                return None, None
        
        def ray_triangle_intersection(self, ray_origin, ray_direction, v0, v1, v2):
            """Algoritmo Möller-Trumbore para intersección ray-triángulo"""
            EPSILON = 0.0000001
            
            edge1 = v1 - v0
            edge2 = v2 - v0
            
            h = np.cross(ray_direction, edge2)
            a = np.dot(edge1, h)
            
            if abs(a) < EPSILON:
                return False, float('inf')
            
            f = 1.0 / a
            s = ray_origin - v0
            u = f * np.dot(s, h)
            
            if u < 0.0 or u > 1.0:
                return False, float('inf')
            
            q = np.cross(s, edge1)
            v = f * np.dot(ray_direction, q)
            
            if v < 0.0 or u + v > 1.0:
                return False, float('inf')
            
            t = f * np.dot(edge2, q)
            
            if t > EPSILON:
                return True, t
            
            return False, float('inf')
        
        def on_mouse_down(self, event):
            """Maneja click del mouse"""
            self.focus_set()
            
            self.last_x = event.x
            self.last_y = event.y
            self.dragging = True
            self.drag_button = event.num
            
            if event.num == 1:
                shift_pressed = (event.state & 0x1) != 0
                self.handle_selection(event.x, event.y, shift_pressed)
                self.dragging = False
                return
            
            if event.num == 3:
                if self.bones_visible and self.bones_data:
                    self.handle_bone_selection(event.x, event.y)
                self.dragging = False
                return
            
            if event.num == 2 and self.mesh_data:
                self.update_pivot_from_mesh()
        
        def on_mouse_up(self, event):
            """Maneja soltar del mouse"""
            self.dragging = False
        
        def on_mouse_move(self, event):
            """Maneja movimiento del mouse"""
            if not self.dragging:
                return
            
            dx = event.x - self.last_x
            dy = event.y - self.last_y
            
            # Detectar si Shift está presionado
            shift_pressed = (event.state & 0x1) != 0
            
            if self.drag_button == 2:
                if shift_pressed:
                    self.pan_x += dx * 0.001 * self.zoom
                    self.pan_y -= dy * 0.001 * self.zoom
                else:
                    self.rotation_y += dx * 0.5
                    self.rotation_x += dy * 0.5
                    self.rotation_x = max(-90, min(90, self.rotation_x))
                
            elif self.drag_button == 3:
                self.pan_x += dx * 0.001 * self.zoom
                self.pan_y -= dy * 0.001 * self.zoom
            
            self.last_x = event.x
            self.last_y = event.y
            self.redraw()
        
        def on_mouse_wheel(self, event):
            """Maneja scroll del mouse"""
            if event.delta > 0:
                self.zoom *= 0.85
            else:
                self.zoom *= 1.15
            
            self.zoom = max(0.5, min(20.0, self.zoom))
            self.redraw()
        
        def on_key_press(self, event):
            """Detecta todas las teclas presionadas"""
            if event.char == 'ç' or event.keysym in ['ccedilla', 'Ccedilla', 'dead_cedilla'] or event.char == '/' or event.keysym == 'slash':
                self.on_isolate_key_pressed(event)
                return "break"
        
        def on_isolate_key_pressed(self, event):
            """Maneja la tecla ç (o /) para aislar/des-aislar partes"""
            if not self.parent_app:
                return
            
            # Si estamos en modo 'all' y hay una parte seleccionada
            if self.viewing_mode == 'all' and self.selected_parts:
                # Obtener el índice de la parte seleccionada
                first_idx = list(self.selected_parts)[0]
                if first_idx < len(self.mesh_data):
                    part_index = self.mesh_data[first_idx].get('part_index', first_idx)
                    # Guardar el índice para reseleccionar al regresar
                    self.isolated_part_index = part_index
                    # Aislar esa parte
                    self.parent_app.seleccionar_parte(part_index)
            elif self.viewing_mode == 'single':
                # Si estamos en modo single, regresar a TODO PERO no recargar UVs
                part_to_reselect = getattr(self, 'isolated_part_index', None)
                self.parent_app.seleccionar_parte(-1, skip_uv_load=True)
                # Reseleccionar la parte después de regresar
                if part_to_reselect is not None and hasattr(self, 'parent_app'):
                    self.after(50, lambda: self.parent_app.reseleccionar_parte(part_to_reselect))
            
            return "break"
        
        def _upload_vbos(self, mesh_data):
            """
            Sube todos los VBOs a VRAM en el momento de carga del mesh.
            Esto se hace una sola vez; redraw() solo emite draw calls.
            Genera para cada subparte:
              - vbo_vertices / vbo_uvs / vbo_indices  → para texture y wireframe
              - vbo_solid_vertices / vbo_solid_colors → para solid (vértices aplanados con color por cara)
            """
            light_dir = np.array([1.0, 1.0, 1.0], dtype=np.float32)
            light_dir /= np.linalg.norm(light_dir)
            ambient  = 0.4
            diffuse  = 1.0
            base_col = np.array([0.8, 0.8, 0.8], dtype=np.float32)

            for parte_data in mesh_data:
                verts = parte_data['vertices']   # ya float32 desde procesar_parte
                tris  = parte_data['triangulos']
                uvs   = parte_data.get('uvs')
                opac  = float(parte_data.get('opacidad', 1.0))

                # ── VBO vértices (texture / wireframe) ──────────────────────
                vbo_v = glGenBuffers(1)
                glBindBuffer(GL_ARRAY_BUFFER, vbo_v)
                glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)

                # ── VBO uvs ──────────────────────────────────────────────────
                vbo_uv = None
                if uvs is not None:
                    uv_arr = uvs if isinstance(uvs, np.ndarray) else np.array(uvs, dtype=np.float32)
                    uv_arr = np.ascontiguousarray(uv_arr, dtype=np.float32)
                    vbo_uv = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_uv)
                    glBufferData(GL_ARRAY_BUFFER, uv_arr.nbytes, uv_arr, GL_STATIC_DRAW)

                # ── VBO índices ──────────────────────────────────────────────
                idx_arr = np.array(tris, dtype=np.uint32).flatten()
                vbo_idx = glGenBuffers(1)
                glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, vbo_idx)
                glBufferData(GL_ELEMENT_ARRAY_BUFFER, idx_arr.nbytes, idx_arr, GL_STATIC_DRAW)

                # ── VBO solid: vértices aplanados + color por cara ───────────
                solid_v_list = []
                solid_c_list = []
                for tri in tris:
                    if not all(i < len(verts) for i in tri):
                        continue
                    v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
                    edge1 = v1 - v0
                    edge2 = v2 - v0
                    normal = np.cross(edge1, edge2)
                    nlen = np.linalg.norm(normal)
                    normal = normal / nlen if nlen > 0 else np.array([0, 1, 0], dtype=np.float32)
                    df = max(0.0, float(np.dot(normal, light_dir)))
                    c  = np.clip(base_col * (ambient + diffuse * df), 0, 1)
                    for v in (v0, v1, v2):
                        solid_v_list.extend(v)
                        solid_c_list.extend([c[0], c[1], c[2], opac])

                vbo_sv = vbo_sc = None
                n_solid = 0
                if solid_v_list:
                    sv_arr = np.array(solid_v_list, dtype=np.float32)
                    sc_arr = np.array(solid_c_list, dtype=np.float32)
                    vbo_sv = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_sv)
                    glBufferData(GL_ARRAY_BUFFER, sv_arr.nbytes, sv_arr, GL_STATIC_DRAW)
                    vbo_sc = glGenBuffers(1)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo_sc)
                    glBufferData(GL_ARRAY_BUFFER, sc_arr.nbytes, sc_arr, GL_STATIC_DRAW)
                    n_solid = len(solid_v_list) // 3

                glBindBuffer(GL_ARRAY_BUFFER, 0)
                glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

                # Guardar handles en el dict — redraw() solo los usa
                parte_data.update({
                    'vbo_vertices':      vbo_v,
                    'vbo_uvs':           vbo_uv,
                    'vbo_indices':       vbo_idx,
                    'vbo_solid_vertices': vbo_sv,
                    'vbo_solid_colors':   vbo_sc,
                    'n_indices':         len(idx_arr),
                    'n_solid':           n_solid,
                })

        def _free_vbos(self, mesh_data):
            """Libera VBOs de VRAM cuando el mesh es reemplazado."""
            if not mesh_data:
                return
            for pd in mesh_data:
                for key in ('vbo_vertices', 'vbo_uvs', 'vbo_indices',
                            'vbo_solid_vertices', 'vbo_solid_colors'):
                    buf = pd.get(key)
                    if buf is not None:
                        try:
                            glDeleteBuffers(1, [buf])
                        except Exception:
                            pass

        def set_mesh_data(self, mesh_data, viewing_mode='all', part_index=-1):
            # Liberar VBOs del mesh anterior
            self._free_vbos(self.mesh_data)
            self.mesh_data = mesh_data
            self.viewing_mode = viewing_mode
            self.current_part_index = part_index
            self.selected_parts.clear()
            self.solid_colors_cache = None  # ya no se usa, pero se mantiene por compatibilidad
            if mesh_data:
                self._upload_vbos(mesh_data)
                self.update_pivot_from_mesh()
            self.redraw()

        def set_render_mode(self, mode):
            # Los VBOs ya están listos para todos los modos — solo cambiar flag y redibujar
            self.render_mode = mode
            self.redraw()

        def precalculate_solid_colors(self):
            # Ya no hace falta: los colores se calculan en _upload_vbos al cargar el mesh.
            pass
        
        def update_pivot_from_mesh(self):
            """Actualiza el punto pivote al centro del modelo"""
            try:
                if not self.mesh_data:
                    return
                
                all_vertices = []
                for parte_data in self.mesh_data:
                    vertices = parte_data['vertices']
                    all_vertices.extend(vertices)
                
                if len(all_vertices) > 0:
                    all_vertices = np.array(all_vertices)
                    center = np.mean(all_vertices, axis=0)
                    self.pivot_x = center[0]
                    self.pivot_y = center[1]
                    self.pivot_z = center[2]
                    
            except:
                pass
        
        def load_texture(self, image_path):
            try:
                from PIL import Image

                img = Image.open(image_path)
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                img_data = np.array(img, dtype=np.uint8)

                if self.texture_id is None:
                    self.texture_id = glGenTextures(1)

                glBindTexture(GL_TEXTURE_2D, self.texture_id)
                # Cerca: linear suave; lejos: mipmap nearest (sin flickering)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)

                fmt = GL_RGB if img.mode == "RGB" else GL_RGBA
                glTexImage2D(GL_TEXTURE_2D, 0, fmt, img.width, img.height, 0, fmt, GL_UNSIGNED_BYTE, img_data)
                glGenerateMipmap(GL_TEXTURE_2D)

                self.redraw()
                return True

            except Exception as e:
                print(f"Error cargando textura: {e}")
                return False
        
        def draw_bones(self):
            """Dibuja todos los huesos como pirámides estilo Blender"""
            if not self.bones_data:
                return
            
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            for bone in self.bones_data:
                self._draw_single_bone(bone)
            
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_BLEND)
        
        def _draw_single_bone(self, bone):
            from app.logic_3d.bones.bone_draw import draw_bone_pyramid
            head = bone['pos_visor']
            tail = bone['tail_visor']
            is_selected = self.selected_bone == bone['idx']
            draw_bone_pyramid(head, tail, bone['bone_id'], is_selected)
        
        def handle_bone_selection(self, x, y):
            if not self.bones_data:
                return

            width  = self.winfo_width()
            height = self.winfo_height()
            if width == 0 or height == 0:
                return

            glClearColor(0.0, 0.0, 0.0, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(45, width / max(height, 1), 0.1, 100.0)

            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            glTranslatef(self.pan_x, self.pan_y, -self.zoom)
            glRotatef(self.rotation_x, 1, 0, 0)
            glRotatef(self.rotation_y, 0, 1, 0)
            glTranslatef(-self.pivot_x, -self.pivot_y, -self.pivot_z)

            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_BLEND)
            glDisable(GL_DITHER)
            glEnable(GL_DEPTH_TEST)

            for bone in self.bones_data:
                color_id = bone['idx'] + 1
                glColor3f((color_id & 0xFF) / 255.0, ((color_id >> 8) & 0xFF) / 255.0, 0.0)
                self._draw_bone_solid(bone)

            gl_y = height - 1 - y
            pixel = glReadPixels(x, gl_y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)

            glClearColor(0.15, 0.15, 0.18, 1.0)
            glEnable(GL_BLEND)

            if isinstance(pixel, (bytes, bytearray)):
                r_read, g_read = pixel[0], pixel[1]
            elif isinstance(pixel, int):
                r_read, g_read = pixel & 0xFF, (pixel >> 8) & 0xFF
            else:
                try:
                    flat = list(pixel.flatten()) if hasattr(pixel, 'flatten') else list(pixel)
                    r_read, g_read = int(flat[0]), int(flat[1])
                except Exception:
                    r_read, g_read = 0, 0

            picked_idx = (r_read | (g_read << 8)) - 1

            if 0 <= picked_idx < len(self.bones_data):
                self.selected_bone = picked_idx
                self.selected_parts.clear()
                if hasattr(self.parent_app, 'update_bone_info'):
                    self.parent_app.update_bone_info(self.bones_data[picked_idx])
            else:
                self.selected_bone = None
                if hasattr(self.parent_app, 'clear_bone_info'):
                    self.parent_app.clear_bone_info()

            self.redraw()

        def _draw_bone_solid(self, bone):
            head = np.array(bone['pos_visor'], dtype=np.float64)
            tail = np.array(bone['tail_visor'], dtype=np.float64)

            direction = tail - head
            length    = np.linalg.norm(direction)

            if length < 0.001:
                length    = 0.05
                direction = np.array([0.0, length, 0.0])
            else:
                direction = direction / length

            width = length * 0.10

            perp = np.cross(direction, np.array([0.0, 1.0, 0.0]))
            if np.linalg.norm(perp) < 0.001:
                perp = np.cross(direction, np.array([1.0, 0.0, 0.0]))
            perp  = perp / np.linalg.norm(perp) * width

            perp2 = np.cross(direction, perp)
            perp2 = perp2 / np.linalg.norm(perp2) * width

            base_center = head + direction * (length * 0.1)
            b1 = base_center + perp
            b2 = base_center + perp2
            b3 = base_center - perp
            b4 = base_center - perp2

            glBegin(GL_TRIANGLES)
            glVertex3fv(tail); glVertex3fv(b1); glVertex3fv(b2)
            glVertex3fv(tail); glVertex3fv(b2); glVertex3fv(b3)
            glVertex3fv(tail); glVertex3fv(b3); glVertex3fv(b4)
            glVertex3fv(tail); glVertex3fv(b4); glVertex3fv(b1)
            glVertex3fv(b1);   glVertex3fv(b3); glVertex3fv(b2)
            glVertex3fv(b1);   glVertex3fv(b4); glVertex3fv(b3)
            glEnd()

        def set_bones_data(self, bones_data, bones_names):
            """Establece datos de huesos."""
            self.bones_data  = bones_data
            self.bones_names = bones_names
            self.selected_bone = None
            self.redraw()

        def toggle_bones(self):
            """Alterna visibilidad de huesos"""
            self.bones_visible = not self.bones_visible
            self.redraw()
            return self.bones_visible

except ImportError:
    GLViewport = None