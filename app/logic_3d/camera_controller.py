from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np


class CameraController:
    def __init__(self):
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
    
    def on_mouse_down(self, event, widget):
        self.last_x = event.x
        self.last_y = event.y
        self.dragging = True
        self.drag_button = event.num
        widget.focus_set()
    
    def on_mouse_up(self, event):
        self.dragging = False
        self.drag_button = None
    
    def on_mouse_move(self, event, widget):
        if not self.dragging:
            return
        
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        
        # Botón central (rueda): rotar
        if self.drag_button == 2:
            self.rotation_y += dx * 0.5
            self.rotation_x += dy * 0.5
            self.rotation_x = max(-89, min(89, self.rotation_x))
            widget.redraw()
        
        # Shift + rueda o botón derecho: pan
        elif self.drag_button == 3 or (self.drag_button == 2 and (event.state & 0x0001)):
            self.pan_x += dx * 0.01
            self.pan_y -= dy * 0.01
            widget.redraw()
        
        self.last_x = event.x
        self.last_y = event.y
    
    def on_mouse_wheel(self, event, widget):
        # Zoom con la rueda del mouse
        if event.delta > 0 or event.num == 4:
            self.zoom *= 0.9
        else:
            self.zoom *= 1.1
        self.zoom = max(0.5, min(50, self.zoom))
        widget.redraw()
    
    def apply_camera_transform(self):
        """Aplica las transformaciones de cámara en OpenGL"""
        glTranslatef(self.pan_x, self.pan_y, -self.zoom)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        glTranslatef(-self.pivot_x, -self.pivot_y, -self.pivot_z)
    
    def unproject_mouse(self, x, y, width, height):
        """Convierte coordenadas de pantalla a coordenadas 3D"""
        viewport = glGetIntegerv(GL_VIEWPORT)
        modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
        projection = glGetDoublev(GL_PROJECTION_MATRIX)
        
        win_y = viewport[3] - y
        
        # Leer profundidad en la posición del mouse
        try:
            z = glReadPixels(x, int(win_y), 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)[0][0]
        except:
            z = 0.5
        
        try:
            pos = gluUnProject(x, win_y, z, modelview, projection, viewport)
            return np.array(pos)
        except:
            return None