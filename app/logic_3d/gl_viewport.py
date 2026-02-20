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
            
            # Cache para colores pre-iluminados en modo sólido
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
            
            # Referencia al label de información (se asigna desde fuera)
            self.info_label = None
            # Referencia a la app principal para poder cambiar de vista
            self.parent_app = None
            
            self.animate = 1
            
            # Trigger inicial para evitar parpadeo
            self.after(100, self._initial_camera_nudge)
        
        def _initial_camera_nudge(self):
            """Hace un pequeño movimiento de cámara al iniciar para evitar parpadeos"""
            try:
                self.rotation_y = 180.1
                self.redraw()
                self.after(50, lambda: setattr(self, 'rotation_y', 180) or self.redraw())
            except:
                # Si falla, reintentar después
                self.after(100, self._initial_camera_nudge)
        
        def initgl(self):
            """Inicializa OpenGL"""
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            
            glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1])
            
            glClearColor(0.15, 0.15, 0.18, 1.0)
            glShadeModel(GL_SMOOTH)
            
            # Habilitar blending para transparencias
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        def redraw(self):
            """Redibuja la escena"""
            try:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                
                # Configurar proyección
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                width = self.winfo_width()
                height = self.winfo_height()
                if height == 0:
                    height = 1
                aspect = width / height
                gluPerspective(45, aspect, 0.1, 100.0)
                
                # Configurar vista
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                
                # Aplicar zoom y pan
                glTranslatef(self.pan_x, self.pan_y, -self.zoom)
                
                # Rotar alrededor del pivote
                glRotatef(self.rotation_x, 1, 0, 0)
                glRotatef(self.rotation_y, 0, 1, 0)
                
                # Trasladar al pivote
                glTranslatef(-self.pivot_x, -self.pivot_y, -self.pivot_z)
                
                # Dibujar grid y modelo solo si hay datos
                if self.mesh_data:
                    self.draw_grid()
                    self.draw_mesh()
                
                try:
                    self.tkSwapBuffers()
                except:
                    pass
            except Exception as e:
                # Contexto OpenGL no está listo, ignorar
                pass
        
        def draw_grid(self):
            """Dibuja el grid de referencia"""
            glDisable(GL_LIGHTING)
            glColor3f(0.25, 0.25, 0.28)
            glBegin(GL_LINES)
            
            size = 2.0
            step = 0.2
            
            for i in np.arange(-size, size + step, step):
                glVertex3f(i, 0, -size)
                glVertex3f(i, 0, size)
                glVertex3f(-size, 0, i)
                glVertex3f(size, 0, i)
            
            glEnd()
            
            # Ejes coordenados
            glLineWidth(3.0)
            glBegin(GL_LINES)
            
            glColor3f(1, 0.2, 0.2)
            glVertex3f(0, 0, 0)
            glVertex3f(0.5, 0, 0)
            
            glColor3f(0.2, 1, 0.2)
            glVertex3f(0, 0, 0)
            glVertex3f(0, 0.5, 0)
            
            glColor3f(0.3, 0.5, 1)
            glVertex3f(0, 0, 0)
            glVertex3f(0, 0, 0.5)
            
            glEnd()
            glLineWidth(1.0)
            
            glEnable(GL_LIGHTING)
        
        def draw_mesh(self):
            """Dibuja el mesh 3D con optimizaciones"""
            if self.render_mode == "wireframe":
                # Modo Wireframe
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                glDisable(GL_LIGHTING)
                glDisable(GL_TEXTURE_2D)
                glLineWidth(1.5)
            else:
                # Modos Solid y Texture
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                
                if self.render_mode == "solid":
                    # Modo Sólido (sin iluminación)
                    glDisable(GL_LIGHTING)
                    glDisable(GL_TEXTURE_2D)
                elif self.render_mode == "texture":
                    # Modo Textura
                    glDisable(GL_LIGHTING)
                    glShadeModel(GL_SMOOTH)
                    if self.texture_id is not None:
                        glEnable(GL_TEXTURE_2D)
                        glBindTexture(GL_TEXTURE_2D, self.texture_id)
                        glColor3f(1.0, 1.0, 1.0)
                    else:
                        glDisable(GL_TEXTURE_2D)
            
            # Dibujar cada parte
            for parte_idx, parte_data in enumerate(self.mesh_data):
                vertices = parte_data['vertices']
                triangulos = parte_data['triangulos']
                uvs = parte_data.get('uvs', None)
                opacidad = parte_data.get('opacidad', 1.0)
                
                # Determinar color según el modo
                if self.render_mode == "texture":
                    # Modo textura: usar color solo si NO hay textura
                    if self.texture_id is None:
                        color = parte_data['color']
                        glColor4f(color[0], color[1], color[2], opacidad)
                    else:
                        glColor4f(1.0, 1.0, 1.0, opacidad)
                
                # Convertir a numpy arrays si no lo están
                if not isinstance(vertices, np.ndarray):
                    vertices = np.array(vertices, dtype=np.float32)
                
                # En modo solid, dibujar cara por cara con colores pre-calculados
                if self.render_mode == "solid":
                    glBegin(GL_TRIANGLES)
                    
                    # Usar colores pre-calculados si existen
                    if self.solid_colors_cache and parte_idx < len(self.solid_colors_cache):
                        face_colors = self.solid_colors_cache[parte_idx]
                        for tri_idx, tri in enumerate(triangulos):
                            if all(i < len(vertices) for i in tri):
                                if tri_idx < len(face_colors):
                                    color = face_colors[tri_idx]
                                    glColor4f(color[0], color[1], color[2], opacidad)
                                else:
                                    glColor4f(0.8, 0.8, 0.8, opacidad)
                                
                                v0 = vertices[tri[0]]
                                v1 = vertices[tri[1]]
                                v2 = vertices[tri[2]]
                                
                                glVertex3f(v0[0], v0[1], v0[2])
                                glVertex3f(v1[0], v1[1], v1[2])
                                glVertex3f(v2[0], v2[1], v2[2])
                    else:
                        # Fallback si no hay cache
                        glColor4f(0.8, 0.8, 0.8, opacidad)
                        for tri in triangulos:
                            if all(i < len(vertices) for i in tri):
                                v0 = vertices[tri[0]]
                                v1 = vertices[tri[1]]
                                v2 = vertices[tri[2]]
                                
                                glVertex3f(v0[0], v0[1], v0[2])
                                glVertex3f(v1[0], v1[1], v1[2])
                                glVertex3f(v2[0], v2[1], v2[2])
                    
                    glEnd()
                else:
                    # Modos texture y wireframe: usar vertex arrays
                    glEnableClientState(GL_VERTEX_ARRAY)
                    glVertexPointer(3, GL_FLOAT, 0, vertices)
                    
                    if self.render_mode == "texture" and self.texture_id is not None and uvs is not None:
                        glEnableClientState(GL_TEXTURE_COORD_ARRAY)
                        if not isinstance(uvs, np.ndarray):
                            uvs = np.array(uvs, dtype=np.float32)
                        glTexCoordPointer(2, GL_FLOAT, 0, uvs)
                    
                    # Crear índice de elementos
                    indices = np.array(triangulos, dtype=np.uint32).flatten()
                    
                    # Dibujar usando glDrawElements
                    glDrawElements(GL_TRIANGLES, len(indices), GL_UNSIGNED_INT, indices)
                    
                    glDisableClientState(GL_VERTEX_ARRAY)
                    if self.render_mode == "texture" and self.texture_id is not None and uvs is not None:
                        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            
            if self.render_mode == "wireframe":
                glLineWidth(1.0)
            
            glDisable(GL_TEXTURE_2D)
            
            # Dibujar bordes de selección
            self.draw_selection_outline()
            
            # Dibujar información de selección
            self.draw_selection_info()
        
        def draw_selection_outline(self):
            """Dibuja bordes amarillos alrededor de las partes seleccionadas"""
            if not self.selected_parts or not self.mesh_data:
                return
            
            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glDisable(GL_DEPTH_TEST)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glLineWidth(4.0)
            glColor3f(1.0, 1.0, 0.0)
            
            for idx in self.selected_parts:
                if idx < len(self.mesh_data):
                    parte_data = self.mesh_data[idx]
                    vertices = parte_data['vertices']
                    triangulos = parte_data['triangulos']
                    
                    glBegin(GL_TRIANGLES)
                    for tri in triangulos:
                        if all(i < len(vertices) for i in tri):
                            glVertex3f(*vertices[tri[0]])
                            glVertex3f(*vertices[tri[1]])
                            glVertex3f(*vertices[tri[2]])
                    glEnd()
            
            glLineWidth(1.0)
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_LIGHTING)
        
        def draw_selection_info(self):
            """Actualiza la información de la parte/subparte seleccionada en el label"""
            if not self.info_label:
                return
            
            if not self.selected_parts or not self.mesh_data:
                self.info_label.configure(text="")
                # Restaurar colores de botones cuando no hay selección en modo TODO
                if self.viewing_mode == 'all' and self.parent_app and hasattr(self.parent_app, 'parte_buttons'):
                    for idx, btn in self.parent_app.parte_buttons.items():
                        if idx == -1:
                            btn.configure(fg_color=("#3B8ED0", "#1F6AA5"))
                        else:
                            btn.configure(fg_color=("gray75", "gray20"))
                return
            
            # En modo 'all', pueden estar seleccionadas múltiples subpartes de UNA parte
            if self.viewing_mode == 'all':
                # Obtener el part_index de cualquier subparte seleccionada
                first_idx = list(self.selected_parts)[0]
                if first_idx < len(self.mesh_data):
                    part_index = self.mesh_data[first_idx].get('part_index', first_idx)
                    label_text = f"Parte {part_index:02d}"
                    
                    # Actualizar colores de botones
                    if self.parent_app and hasattr(self.parent_app, 'parte_buttons'):
                        for idx, btn in self.parent_app.parte_buttons.items():
                            if idx == -1:
                                btn.configure(fg_color=("#3B8ED0", "#1F6AA5"))
                            elif idx == part_index:
                                btn.configure(fg_color=("#FFD700", "#DAA520"))
                            else:
                                btn.configure(fg_color=("gray75", "gray20"))
                    
                    # Calcular totales de TODA la parte
                    total_vertices = 0
                    total_triangulos = 0
                    total_edges = set()
                    num_subpartes = 0
                    
                    for idx in self.selected_parts:
                        if idx < len(self.mesh_data):
                            mesh_data = self.mesh_data[idx]
                            total_vertices += len(mesh_data['vertices'])
                            total_triangulos += len(mesh_data['triangulos'])
                            num_subpartes += 1
                            for tri in mesh_data['triangulos']:
                                total_edges.add(tuple(sorted([tri[0], tri[1]])))
                                total_edges.add(tuple(sorted([tri[1], tri[2]])))
                                total_edges.add(tuple(sorted([tri[2], tri[0]])))
                    
                    info_text = f"{label_text}\n{total_vertices} Vértices\n{total_triangulos} Caras\n{len(total_edges)} Edges\n{num_subpartes} SubPartes"
                    self.info_label.configure(text=info_text)
            else:
                # Modo 'single': solo se selecciona UNA subparte
                if len(self.selected_parts) == 1:
                    idx = list(self.selected_parts)[0]
                    if idx < len(self.mesh_data):
                        parte_data = self.mesh_data[idx]
                        num_vertices = len(parte_data['vertices'])
                        num_triangulos = len(parte_data['triangulos'])
                        
                        # Calcular número de edges
                        edges = set()
                        for tri in parte_data['triangulos']:
                            edges.add(tuple(sorted([tri[0], tri[1]])))
                            edges.add(tuple(sorted([tri[1], tri[2]])))
                            edges.add(tuple(sorted([tri[2], tri[0]])))
                        num_edges = len(edges)
                        
                        label_text = f"Subparte {idx:02d}"
                        info_text = f"{label_text}\n{num_vertices} Vértices\n{num_triangulos} Caras\n{num_edges} Edges"
                        self.info_label.configure(text=info_text)
                else:
                    self.info_label.configure(text="")
        
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
            
            # Click izquierdo - selección
            if event.num == 1:
                shift_pressed = (event.state & 0x1) != 0
                self.handle_selection(event.x, event.y, shift_pressed)
                self.dragging = False
                return
            
            # Si es click medio (rotar), actualizar pivote al centro del modelo
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
        
        def set_mesh_data(self, mesh_data, viewing_mode='all', part_index=-1):
            """Establece los datos del mesh"""
            self.mesh_data = mesh_data
            self.viewing_mode = viewing_mode
            self.current_part_index = part_index
            self.selected_parts.clear()
            self.solid_colors_cache = None
            if mesh_data:
                self.update_pivot_from_mesh()
            self.redraw()
        
        def set_render_mode(self, mode):
            """Cambia el modo de renderizado (solid, texture, wireframe)"""
            self.render_mode = mode
            # Pre-calcular colores para modo sólido
            if mode == "solid" and self.mesh_data:
                self.precalculate_solid_colors()
            self.redraw()
        
        def precalculate_solid_colors(self):
            """Pre-calcula los colores iluminados para modo sólido (optimización)"""
            if not self.mesh_data:
                return
            
            self.solid_colors_cache = []
            
            # Configuración de luz fija
            light_dir = np.array([1.0, 1.0, 1.0])
            light_dir = light_dir / np.linalg.norm(light_dir)
            ambient = 0.4
            diffuse = 1.0
            base_color = np.array([0.8, 0.8, 0.8])
            
            for parte_data in self.mesh_data:
                vertices = parte_data['vertices']
                triangulos = parte_data['triangulos']
                
                face_colors = []
                
                for tri in triangulos:
                    if all(i < len(vertices) for i in tri):
                        v0 = vertices[tri[0]]
                        v1 = vertices[tri[1]]
                        v2 = vertices[tri[2]]
                        
                        # Calcular normal de la cara
                        edge1 = v1 - v0
                        edge2 = v2 - v0
                        normal = np.cross(edge1, edge2)
                        norm_length = np.linalg.norm(normal)
                        if norm_length > 0:
                            normal = normal / norm_length
                        else:
                            normal = np.array([0.0, 1.0, 0.0])
                        
                        # Calcular iluminación
                        diffuse_factor = max(0.0, np.dot(normal, light_dir))
                        final_color = base_color * (ambient + diffuse * diffuse_factor)
                        final_color = np.clip(final_color, 0.0, 1.0)
                        
                        face_colors.append(final_color)
                    else:
                        face_colors.append(base_color)
                
                self.solid_colors_cache.append(face_colors)
        
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
            """Carga una textura desde un archivo PNG"""
            try:
                from PIL import Image
                
                img = Image.open(image_path)
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                img_data = np.array(img, dtype=np.uint8)
                
                if self.texture_id is None:
                    self.texture_id = glGenTextures(1)
                
                glBindTexture(GL_TEXTURE_2D, self.texture_id)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                
                if img.mode == "RGB":
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 
                               0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
                elif img.mode == "RGBA":
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 
                               0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
                
                self.redraw()
                return True
                
            except Exception as e:
                print(f"Error cargando textura: {e}")
                return False

except ImportError:
    GLViewport = None