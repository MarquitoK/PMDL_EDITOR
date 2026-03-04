import struct
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

try:
    import numpy as np
    from OpenGL.GL import *
    from OpenGL.GLU import *
    from pyopengltk import OpenGLFrame
    _GL_OK = True
except ImportError:
    _GL_OK = False


# Diálogo para elegir ID de hueso
class BonePickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, used_ids: set, names: dict):
        super().__init__(parent)
        self.title("Elegir ID del nuevo hueso")
        self.resizable(False, True)
        self.result = None
        self.grab_set()

        ctk.CTkLabel(self, text="Selecciona el ID del nuevo hueso:",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(padx=12, pady=(12, 4), anchor="w")

        frame = ctk.CTkScrollableFrame(self, fg_color=("#f5f5f5", "#1e1e2e"))
        frame.pack(fill="both", expand=True, padx=8, pady=4)

        self._var = tk.IntVar(value=-1)
        for bid in range(0x00, 0xFF):
            if bid in used_ids:
                continue
            sk    = f"sk_{bid:02X}"
            name  = names.get(sk, "")
            label = f"{name} ({bid:02X})" if name else f"({bid:02X})"
            ctk.CTkRadioButton(frame, text=label, variable=self._var,
                               value=bid, font=ctk.CTkFont(size=11)
                               ).pack(anchor="w", padx=8, pady=1)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=8)
        ctk.CTkButton(btn_row, text="Aceptar", command=self._ok,
                      fg_color=("#28a745","#1e7e34")
                      ).pack(side="left", padx=4, expand=True, fill="x")
        ctk.CTkButton(btn_row, text="Cancelar", command=self.destroy,
                      fg_color=("gray65","gray30")
                      ).pack(side="left", padx=4, expand=True, fill="x")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

        # #3: centrar sobre la ventana padre
        self.update_idletasks()
        pw = parent.winfo_width();  ph = parent.winfo_height()
        px = parent.winfo_rootx(); py = parent.winfo_rooty()
        dw, dh = 320, 480
        self.geometry(f"{dw}x{dh}+{px + (pw-dw)//2}+{py + (ph-dh)//2}")

    def _ok(self):
        v = self._var.get()
        if v == -1:
            messagebox.showwarning("Sin selección", "Elige un hueso de la lista.", parent=self)
            return
        self.result = v
        self.destroy()


# Viewport 3D
if _GL_OK:
    class BoneViewport(OpenGLFrame):
        def __init__(self, master, on_bone_picked=None, **kwargs):
            super().__init__(master, **kwargs)
            self.bones_data     = []
            self.selected_idx   = None
            self.on_bone_picked = on_bone_picked

            self.rotation_x = 20.0
            self.rotation_y = 180.0
            self.zoom        = 10.0
            self.pan_x = self.pan_y = 0.0
            self.last_x = self.last_y = 0
            self.dragging = False; self.drag_button = None

            self.bind("<ButtonPress-1>",   self._pick)
            self.bind("<ButtonRelease-1>", self._mouse_up)
            self.bind("<B1-Motion>",       self._mouse_move)
            self.bind("<ButtonPress-2>",   self._mouse_down)
            self.bind("<ButtonPress-3>",   self._mouse_down)
            self.bind("<ButtonRelease-2>", self._mouse_up)
            self.bind("<ButtonRelease-3>", self._mouse_up)
            self.bind("<B2-Motion>",       self._mouse_move)
            self.bind("<B3-Motion>",       self._mouse_move)
            self.bind("<MouseWheel>",      self._scroll)

        def initgl(self):
            glClearColor(0.13, 0.13, 0.16, 1.0)
            glEnable(GL_DEPTH_TEST); glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            self._gl_ready = True
            # Notificar al editor para que haga el primer redraw
            if self.on_bone_picked is not None:
                # Reutilizamos el after del master para disparar micro_rotate
                try:
                    self.after(50, self._do_first_draw)
                except Exception:
                    pass

        def _do_first_draw(self):
            try:
                self.redraw()
            except Exception:
                pass

        def _apply_camera(self):
            w = self.winfo_width(); h = self.winfo_height() or 1
            glViewport(0, 0, w, h)
            glMatrixMode(GL_PROJECTION); glLoadIdentity()
            gluPerspective(45, w/h, 0.01, 200.0)
            glMatrixMode(GL_MODELVIEW); glLoadIdentity()
            glTranslatef(self.pan_x, self.pan_y, -self.zoom)
            glRotatef(self.rotation_x, 1, 0, 0)
            glRotatef(self.rotation_y, 0, 1, 0)

        def redraw(self):
            try:
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                self._apply_camera()
                self._draw_grid()
                self._draw_bones_visual()
                try: self.tkSwapBuffers()
                except Exception: pass
            except Exception: pass

        def _draw_grid(self):
            glDisable(GL_DEPTH_TEST)
            glColor4f(0.3, 0.3, 0.3, 0.5); glLineWidth(1.0)
            glBegin(GL_LINES)
            for i in range(-5, 6):
                glVertex3f(i*0.5, 0, -2.5); glVertex3f(i*0.5, 0,  2.5)
                glVertex3f(-2.5, 0, i*0.5); glVertex3f( 2.5, 0, i*0.5)
            glEnd()
            glEnable(GL_DEPTH_TEST)

        def _draw_bones_visual(self):
            if not self.bones_data: return
            glDisable(GL_DEPTH_TEST); glEnable(GL_BLEND)
            for bone in self.bones_data:
                self._draw_pyramid(bone, picking=False)
            glEnable(GL_DEPTH_TEST)

        def _pyramid_geometry(self, bone):
            head = np.array(bone['pos_visor'], dtype=np.float64)
            tail = np.array(bone.get('tail_visor', bone['pos_visor']), dtype=np.float64)
            d = tail - head
            ln = np.linalg.norm(d)
            if ln < 0.001: ln = 0.05; d = np.array([0., ln, 0.])
            else: d = d / ln
            w = ln * 0.10
            perp = np.cross(d, np.array([0., 1., 0.]))
            if np.linalg.norm(perp) < 0.001: perp = np.cross(d, np.array([1., 0., 0.]))
            perp = perp / np.linalg.norm(perp) * w
            perp2 = np.cross(d, perp); perp2 = perp2 / np.linalg.norm(perp2) * w
            base_center = head + d * (ln * 0.1)
            b1=base_center+perp; b2=base_center+perp2; b3=base_center-perp; b4=base_center-perp2
            return tail, b1, b2, b3, b4

        def _draw_pyramid(self, bone, picking=False):
            import hashlib
            tip, b1, b2, b3, b4 = self._pyramid_geometry(bone)
            if not picking:
                if self.selected_idx == bone['idx']:
                    glColor4f(1.0, 0.85, 0.0, 0.95)
                else:
                    h = hashlib.md5(str(bone['bone_id']).encode()).digest()
                    glColor4f(h[0]/255, h[1]/255, h[2]/255, 0.85)
            glBegin(GL_TRIANGLES)
            glVertex3fv(tip); glVertex3fv(b1); glVertex3fv(b2)
            glVertex3fv(tip); glVertex3fv(b2); glVertex3fv(b3)
            glVertex3fv(tip); glVertex3fv(b3); glVertex3fv(b4)
            glVertex3fv(tip); glVertex3fv(b4); glVertex3fv(b1)
            glVertex3fv(b1); glVertex3fv(b3); glVertex3fv(b2)
            glVertex3fv(b1); glVertex3fv(b4); glVertex3fv(b3)
            glEnd()
            if not picking and self.selected_idx == bone['idx']:
                glLineWidth(2.0); glColor3f(1., 1., 0.)
                glBegin(GL_LINE_LOOP)
                for v in [b1,b2,b3,b4]: glVertex3fv(v)
                glEnd()
                glBegin(GL_LINES)
                for v in [b1,b2,b3,b4]: glVertex3fv(tip); glVertex3fv(v)
                glEnd()
                glLineWidth(1.0)

        def _pick(self, event):
            self.focus_set()
            if not self.bones_data:
                # sin huesos: iniciar drag de todas formas
                self.last_x, self.last_y = event.x, event.y
                self.dragging = True; self.drag_button = 1
                return "break"
            x, y = event.x, event.y
            h = self.winfo_height() or 1
            # Render de picking en color ID
            glClearColor(0., 0., 0., 1.)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self._apply_camera()
            glDisable(GL_BLEND); glDisable(GL_DITHER); glEnable(GL_DEPTH_TEST)
            for bone in self.bones_data:
                cid = bone['idx'] + 1
                glColor3f((cid & 0xFF) / 255., ((cid >> 8) & 0xFF) / 255., 0.)
                self._draw_pyramid(bone, picking=True)
            glFlush()
            try:
                glReadBuffer(GL_BACK)
            except Exception:
                pass
            pixel = glReadPixels(x, h - 1 - y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
            glClearColor(0.13, 0.13, 0.16, 1.); glEnable(GL_BLEND)
            try:
                if isinstance(pixel, (bytes, bytearray)): r, g = pixel[0], pixel[1]
                elif isinstance(pixel, int): r, g = pixel & 0xFF, (pixel >> 8) & 0xFF
                else:
                    flat = list(pixel.flatten()) if hasattr(pixel, 'flatten') else list(pixel)
                    r, g = int(flat[0]), int(flat[1])
            except Exception: r, g = 0, 0
            picked = (r | (g << 8)) - 1
            if 0 <= picked < len(self.bones_data):
                self.selected_idx = picked
                if self.on_bone_picked: self.on_bone_picked(picked)
            else:
                self.last_x, self.last_y = event.x, event.y
                self.dragging = True; self.drag_button = 1
            self.redraw()
            return "break"

        def _mouse_down(self, e):
            self.focus_set(); self.last_x,self.last_y=e.x,e.y
            self.dragging=True; self.drag_button=e.num
        def _mouse_up(self, e): self.dragging=False
        def _mouse_move(self, e):
            if not self.dragging: return
            dx,dy=e.x-self.last_x,e.y-self.last_y
            if self.drag_button==2:
                if e.state&0x1: self.pan_x+=dx*0.001*self.zoom; self.pan_y-=dy*0.001*self.zoom
                else: self.rotation_y+=dx*0.5; self.rotation_x=max(-90,min(90,self.rotation_x+dy*0.5))
            elif self.drag_button==3:
                self.pan_x+=dx*0.001*self.zoom; self.pan_y-=dy*0.001*self.zoom
            self.last_x,self.last_y=e.x,e.y; self.redraw()
        def _scroll(self, e):
            self.zoom*=0.85 if e.delta>0 else 1.15
            self.zoom=max(0.1,min(100.,self.zoom)); self.redraw()

        # #1: set_bones resetea cámara
        def set_bones(self, bones_data):
            """Carga inicial — resetea cámara al centroide."""
            self.bones_data = bones_data; self.selected_idx = None
            if bones_data:
                pts = [b['pos_visor'] for b in bones_data]
                self.pan_x = -sum(p[0] for p in pts)/len(pts)
                self.pan_y = -sum(p[1] for p in pts)/len(pts)
            self.redraw()

        def update_bones(self, bones_data):
            """Actualiza datos sin tocar la cámara."""
            self.bones_data = bones_data
            self.redraw()

        def highlight(self, bone_idx):
            self.selected_idx = bone_idx; self.redraw()

else:
    class BoneViewport(tk.Frame):
        def __init__(self, master, on_bone_picked=None, **kwargs):
            super().__init__(master, bg="#1a1a2e", **kwargs)
            tk.Label(self, text="OpenGL no disponible\npip install pyopengltk PyOpenGL",
                     bg="#1a1a2e", fg="gray", justify="center").pack(expand=True)
        def set_bones(self, _): pass
        def update_bones(self, _): pass
        def highlight(self, _): pass
        def redraw(self): pass

# Nodo del árbol
class BoneTreeNode(tk.Frame):
    INDENT = 14
    def __init__(self, master, bone, depth, names, on_select, on_toggle_collapse,
                 has_children=False, **kwargs):
        super().__init__(master, bg="#1e1e2e", **kwargs)
        self.bone=bone; self.on_select=on_select; self.on_toggle=on_toggle_collapse
        self.has_children=has_children; self._selected=False
        bid=bone['bone_id']; sk=f"sk_{bid:02X}"; name=names.get(sk,"")
        label=f"{name} ({bid:02X})" if name else f"({bid:02X})"
        if depth>0: tk.Frame(self,width=depth*self.INDENT,bg="#1e1e2e").pack(side="left")
        if has_children:
            self.arrow=tk.Label(self,text="▼",bg="#1e1e2e",fg="#888888",
                                font=("Segoe UI",8),cursor="hand2",width=2)
            self.arrow.pack(side="left")
            self.arrow.bind("<Button-1>",lambda e:self.on_toggle(self))
        else:
            tk.Label(self,text=" ",bg="#1e1e2e",width=2,font=("Segoe UI",8)).pack(side="left")
        self.lbl=tk.Label(self,text=label,bg="#1e1e2e",fg="#cccccc",
                          font=("Segoe UI",10),anchor="w",cursor="hand2")
        self.lbl.pack(side="left",fill="x",expand=True)
        for w in (self,self.lbl): w.bind("<Button-1>",lambda e:self.on_select(self))

    def set_selected(self,val):
        self._selected=val
        bg="#1F6AA5" if val else "#1e1e2e"; fg="#ffffff" if val else "#cccccc"
        self.configure(bg=bg); self.lbl.configure(bg=bg,fg=fg)
        if self.has_children: self.arrow.configure(bg=bg)

    def set_collapsed(self,collapsed):
        if self.has_children: self.arrow.configure(text="▶" if collapsed else "▼")



# Árbol
class BoneTree(ctk.CTkScrollableFrame):
    def __init__(self, master, on_bone_selected, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="#1e1e2e")
        self.on_bone_selected = on_bone_selected
        self.nodes={}; self.collapsed=set(); self.bones_data=[]; self.names={}
        self._selected_node=None; self._subtree={}
        # Orden canónico: lista de idx en el orden de aparición en el árbol
        self._display_order = []

    def load(self, bones_data, names):
        self.bones_data=bones_data; self.names=names
        self.collapsed=set(); self._selected_node=None
        self._full_rebuild()

    def _compute_display_order(self):
        """Orden DFS de los huesos — mismo orden que bones_data (ya está en DFS)."""
        self._display_order = [b['idx'] for b in self.bones_data]

    def _full_rebuild(self):
        for w in self.winfo_children(): w.destroy()
        self.nodes={}; self._subtree={}

        children_of={i:[] for i in range(len(self.bones_data))}
        for b in self.bones_data:
            if b['padre_idx'] is not None:
                children_of[b['padre_idx']].append(b['idx'])

        depth_of={}
        def get_depth(idx):
            if idx in depth_of: return depth_of[idx]
            p=self.bones_data[idx]['padre_idx']
            d=0 if p is None else get_depth(p)+1
            depth_of[idx]=d; return d
        for b in self.bones_data: get_depth(b['idx'])

        def get_subtree(idx):
            r=[]
            for c in children_of.get(idx,[]):
                r.append(c); r.extend(get_subtree(c))
            return r
        for b in self.bones_data: self._subtree[b['idx']]=get_subtree(b['idx'])

        self._compute_display_order()

        for bone in self.bones_data:
            idx=bone['idx']
            node=BoneTreeNode(self,bone,depth_of[idx],self.names,
                              on_select=self._on_select,
                              on_toggle_collapse=self._on_collapse,
                              has_children=bool(children_of[idx]))
            node.pack(fill="x",pady=0,padx=0,ipady=1)
            if idx in self.collapsed: node.set_collapsed(True)
            self.nodes[idx]=node

        for idx in self.collapsed: self._hide_subtree(idx)

    def _hide_subtree(self, parent_idx):
        for desc in self._subtree.get(parent_idx,[]):
            if desc in self.nodes: self.nodes[desc].pack_forget()

    def _show_subtree(self, parent_idx):
        for desc in self._subtree.get(parent_idx, []):
            if desc not in self.nodes: continue
            # ¿Debe estar visible?
            if self._is_blocked(desc): continue
            # Encontrar el predecesor visible en display_order
            node = self.nodes[desc]
            prev = self._prev_visible(desc)
            if prev is not None:
                node.pack(fill="x", pady=0, padx=0, ipady=1, after=self.nodes[prev])
            else:
                node.pack(fill="x", pady=0, padx=0, ipady=1)

    def _is_blocked(self, idx):
        """True si algún ancestro (excepto el propio idx) está colapsado."""
        p = self.bones_data[idx]['padre_idx']
        while p is not None:
            if p in self.collapsed: return True
            p = self.bones_data[p]['padre_idx']
        return False

    def _prev_visible(self, idx):
        """Retorna el idx del nodo visible inmediatamente anterior en display_order."""
        pos = self._display_order.index(idx) if idx in self._display_order else -1
        for i in range(pos-1, -1, -1):
            candidate = self._display_order[i]
            if candidate in self.nodes and not self._is_blocked(candidate):
                return candidate
        return None

    def _on_select(self, node):
        if self._selected_node: self._selected_node.set_selected(False)
        self._selected_node=node; node.set_selected(True)
        self.on_bone_selected(node.bone)

    def _on_collapse(self, node):
        idx=node.bone['idx']
        if idx in self.collapsed:
            self.collapsed.discard(idx); node.set_collapsed(False)
            self._show_subtree(idx)
        else:
            self.collapsed.add(idx); node.set_collapsed(True)
            self._hide_subtree(idx)

    def select_bone(self, idx):
        """Selecciona el nodo, sin expandir (para uso interno del árbol)."""
        if self._selected_node: self._selected_node.set_selected(False)
        if idx in self.nodes:
            self._selected_node=self.nodes[idx]; self._selected_node.set_selected(True)

    def select_and_reveal(self, idx):
        """#5: Expande todos los ancestros colapsados y luego selecciona."""
        # Recopilar ancestros que están colapsados
        to_expand = []
        p = self.bones_data[idx]['padre_idx'] if idx < len(self.bones_data) else None
        while p is not None:
            if p in self.collapsed:
                to_expand.append(p)
            p = self.bones_data[p]['padre_idx']
        # Expandir de raíz a hoja (orden inverso)
        for anc in reversed(to_expand):
            if anc in self.nodes:
                self.collapsed.discard(anc)
                self.nodes[anc].set_collapsed(False)
                self._show_subtree(anc)
        self.select_bone(idx)

    def add_node_after(self, bone, parent_idx, all_bones):
        """#4 fix: inserta el nodo nuevo visualmente en la posición correcta."""
        # Recalcular subtrees y display_order
        self.bones_data = all_bones
        self._subtree={}
        children_of={i:[] for i in range(len(all_bones))}
        for b in all_bones:
            if b['padre_idx'] is not None:
                children_of[b['padre_idx']].append(b['idx'])
        def get_subtree(idx):
            r=[]
            for c in children_of.get(idx,[]):
                r.append(c); r.extend(get_subtree(c))
            return r
        for b in all_bones: self._subtree[b['idx']]=get_subtree(b['idx'])
        self._compute_display_order()

        # Calcular depth
        def get_depth(idx):
            p=all_bones[idx]['padre_idx']
            return 0 if p is None else get_depth(p)+1

        new_idx = bone['idx']
        node = BoneTreeNode(self, bone, get_depth(new_idx), self.names,
                            on_select=self._on_select,
                            on_toggle_collapse=self._on_collapse,
                            has_children=False)
        self.nodes[new_idx] = node

        # Insertar después del predecesor visible
        prev = self._prev_visible(new_idx)
        if prev is not None:
            node.pack(fill="x", pady=0, padx=0, ipady=1, after=self.nodes[prev])
        else:
            node.pack(fill="x", pady=0, padx=0, ipady=1)

        # Dar flecha al padre si aún no tiene
        if parent_idx in self.nodes:
            p_node=self.nodes[parent_idx]
            if not p_node.has_children:
                p_node.has_children=True
                for child in p_node.winfo_children():
                    if isinstance(child,tk.Label) and child.cget("text")==" ":
                        child.destroy(); break
                arrow=tk.Label(p_node,text="▼",bg=p_node.cget("bg"),fg="#888888",
                               font=("Segoe UI",8),cursor="hand2",width=2)
                arrow.pack(side="left",before=p_node.lbl)
                arrow.bind("<Button-1>",lambda e,n=p_node:self._on_collapse(n))
                p_node.arrow=arrow

# Panel de propiedades
class SpinEntry(tk.Frame):
    def __init__(self, master, width=80, **kwargs):
        super().__init__(master, bg="#2b2b2b", **kwargs)
        self._var = tk.StringVar(value="0.0000")
        inner = tk.Frame(self, bg="#2b2b2b", bd=1, relief="flat",
                         highlightthickness=1, highlightbackground="#555")
        inner.pack(fill="both", expand=True)

        self._entry = tk.Entry(inner, textvariable=self._var, width=max(1, width//9),
                               bg="#1a1a2e", fg="white", insertbackground="white",
                               relief="flat", font=("Segoe UI", 11), bd=2)
        self._entry.pack(side="left", fill="both", expand=True)

        btn_col = tk.Frame(inner, bg="#2b2b2b", width=22)
        btn_col.pack(side="right", fill="y")
        btn_col.pack_propagate(False)

        btn_up = tk.Label(btn_col, text="▲", bg="#333", fg="#bbb",
                          font=("Segoe UI", 9), cursor="hand2")
        btn_up.pack(fill="both", expand=True)
        btn_dn = tk.Label(btn_col, text="▼", bg="#333", fg="#bbb",
                          font=("Segoe UI", 9), cursor="hand2")
        btn_dn.pack(fill="both", expand=True)

        btn_up.bind("<Button-1>", lambda e: self._step(+1))
        btn_dn.bind("<Button-1>", lambda e: self._step(-1))
        btn_up.bind("<Enter>", lambda e: btn_up.configure(bg="#444"))
        btn_up.bind("<Leave>", lambda e: btn_up.configure(bg="#333"))
        btn_dn.bind("<Enter>", lambda e: btn_dn.configure(bg="#444"))
        btn_dn.bind("<Leave>", lambda e: btn_dn.configure(bg="#333"))

    def _step(self, delta):
        try:
            val = float(self._var.get())
        except ValueError:
            val = 0.0
        self._var.set(f"{val + delta:.4f}")

    def get(self):
        return self._var.get()

    def delete(self, a, b):
        self._var.set("")

    def insert(self, pos, val):
        self._var.set(str(val))


class BonePropertiesPanel(ctk.CTkFrame):
    def __init__(self, master, on_apply, **kwargs):
        super().__init__(master, **kwargs)
        self.on_apply=on_apply; self._bone=None
        ctk.CTkLabel(self,text="Propiedades",font=ctk.CTkFont(size=13,weight="bold")
                     ).pack(anchor="w",padx=10,pady=(10,2))
        # Frame para info del hueso
        self._info_frame = tk.Frame(self, bg="#1e1e2e")
        self._info_frame.pack(fill="x", padx=10, pady=(0,6))
        self.after(0, self._show_placeholder)
        ctk.CTkFrame(self,height=1,fg_color=("gray70","gray30")).pack(fill="x",padx=8,pady=4)

        ctk.CTkLabel(self,text="Posición Global del Hueso",
                     font=ctk.CTkFont(size=11,weight="bold")
                     ).pack(anchor="w",padx=10,pady=(6,4))
        xyz_frame=ctk.CTkFrame(self,fg_color="transparent")
        xyz_frame.pack(fill="x",padx=10,pady=2)
        for lbl, attr in [("X","entry_x"),("Y","entry_y"),("Z","entry_z")]:
            row = tk.Frame(xyz_frame, bg="#2b2b2b")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=lbl, bg="#2b2b2b", fg="#aaaaaa",
                     font=("Segoe UI", 10), width=2).pack(side="left", padx=(2,4))
            e = SpinEntry(row, width=160)
            e.pack(side="left", fill="x", expand=True, ipady=4)
            setattr(self, attr, e)

        self.btn_apply=ctk.CTkButton(self,text="✔ Aplicar posición",command=self._apply,
                                     height=30,font=ctk.CTkFont(size=13),
                                     fg_color=("#28a745","#1e7e34"),
                                     hover_color=("#218838","#155724"),state="disabled")
        self.btn_apply.pack(fill="x",padx=10,pady=(10,4))

        ctk.CTkFrame(self,height=1,fg_color=("gray70","gray30")).pack(fill="x",padx=8,pady=4)
        btn_row=ctk.CTkFrame(self,fg_color="transparent")
        btn_row.pack(fill="x",padx=10,pady=4)
        self.btn_add=ctk.CTkButton(btn_row,text="➕ Hijo",command=self._add_child,
                                   height=30,font=ctk.CTkFont(size=13),
                                   fg_color=("#3B8ED0","#1F6AA5"),state="disabled",width=90)
        self.btn_add.pack(side="left",padx=(0,4))
        self.btn_del=ctk.CTkButton(btn_row,text="🗑 Eliminar",command=self._delete,
                                   height=30,font=ctk.CTkFont(size=13),
                                   fg_color=("#dc3545","#a71d2a"),
                                   hover_color=("#c82333","#8b1623"),
                                   state="disabled",width=110)
        self.btn_del.pack(side="left")

    def load_bone(self, bone, names, bones_data=None):
        self._bone = bone
        bid = bone['bone_id']
        sk  = f"sk_{bid:02X}"
        name = names.get(sk, "")

        # Limpiar sub-labels anteriores
        for w in self._info_frame.winfo_children():
            w.destroy()

        # Línea 1: "Hueso:"
        row1 = tk.Frame(self._info_frame, bg="#1e1e2e")
        row1.pack(anchor="w", fill="x")
        head = f"Hueso {bid:02X}" + (" -" if name else "")
        tk.Label(row1, text=head, bg="#1e1e2e", fg="white",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        if name:
            tk.Label(row1, text=f" {name}", bg="#1e1e2e", fg="#FFD700",
                     font=("Segoe UI", 10, "bold")).pack(side="left")

        # Línea 2: relación jerárquica
        row2 = tk.Frame(self._info_frame, bg="#1e1e2e")
        row2.pack(anchor="w", fill="x", pady=(2, 0))
        if bone['padre_idx'] is None:
            tk.Label(row2, text="Padre", bg="#1e1e2e", fg="white",
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            tk.Label(row2, text=" - (Raiz)", bg="#1e1e2e", fg="#aaaaaa",
                     font=("Segoe UI", 9)).pack(side="left")
        else:
            tk.Label(row2, text="Hijo de:", bg="#1e1e2e", fg="white",
                     font=("Segoe UI", 9, "bold")).pack(side="left")
            p_idx = bone['padre_idx']
            if bones_data and p_idx < len(bones_data):
                pid   = bones_data[p_idx]['bone_id']
                psk   = f"sk_{pid:02X}"
                pname = names.get(psk, "")
                phead = f" Hueso {pid:02X}" + (" -" if pname else "")
                tk.Label(row2, text=phead, bg="#1e1e2e", fg="white",
                         font=("Segoe UI", 9)).pack(side="left")
                if pname:
                    tk.Label(row2, text=f" {pname}", bg="#1e1e2e", fg="#FFD700",
                             font=("Segoe UI", 9, "bold")).pack(side="left")
            else:
                tk.Label(row2, text=" Hueso ?", bg="#1e1e2e", fg="white",
                         font=("Segoe UI", 9)).pack(side="left")

        px, py, pz = bone['pos']
        for e, v in zip((self.entry_x, self.entry_y, self.entry_z), (px, py, pz)):
            e.delete(0, "end"); e.insert(0, f"{v:.4f}")
        for w in (self.btn_apply, self.btn_add, self.btn_del):
            w.configure(state="normal")

    def _show_placeholder(self):
        for w in self._info_frame.winfo_children():
            w.destroy()
        r1 = tk.Frame(self._info_frame, bg="#1e1e2e")
        r1.pack(anchor="w", fill="x")
        tk.Label(r1, text="Editor de Huesos", bg="#1e1e2e", fg="#FFD700",
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(r1, text=" (Beta) - By ", bg="#1e1e2e", fg="white",
                 font=("Segoe UI", 10)).pack(side="left")
        r2 = tk.Frame(self._info_frame, bg="#1e1e2e")
        r2.pack(anchor="w", fill="x", pady=(1,0))
        tk.Label(r2, text="Los ijue30s", bg="#1e1e2e", fg="#FFD700",
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Label(r2, text=" con la colaboración de ", bg="#1e1e2e", fg="white",
                 font=("Segoe UI", 10)).pack(side="left")
        r3 = tk.Frame(self._info_frame, bg="#1e1e2e")
        r3.pack(anchor="w", fill="x", pady=(1,0))
        tk.Label(r3, text="KASTO MD ダ", bg="#1e1e2e", fg="#FFD700",
                 font=("Segoe UI", 10)).pack(side="left")

    def clear(self):
        self._bone=None
        self._show_placeholder()
        for e in (self.entry_x,self.entry_y,self.entry_z): e.delete(0,"end")
        for w in (self.btn_apply,self.btn_add,self.btn_del):
            w.configure(state="disabled")

    def _apply(self):
        if not self._bone: return
        try:
            head = tuple(float(e.get()) for e in (self.entry_x,self.entry_y,self.entry_z))
            self.on_apply(self._bone['idx'], head, action="move")
        except ValueError: messagebox.showerror("Error","Ingresa valores numéricos válidos.")

    def _add_child(self):
        if self._bone: self.on_apply(self._bone['idx'],None,action="add_child")

    def _delete(self):
        if not self._bone: return
        self.on_apply(self._bone['idx'], None, action="confirm_delete")



# Lógica binaria  (#6: preservar bytes del bloque raw)

def reconstruir_bloque_huesos(bones_data):
    # Recalcular pop_level
    pila = []
    for i, bone in enumerate(bones_data):
        pila.append(bone['idx'])
        if i + 1 < len(bones_data):
            next_padre = bones_data[i + 1]['padre_idx']
            pops = 0
            if next_padre is None:
                pops = len(pila); pila.clear()
            else:
                while pila and pila[-1] != next_padre:
                    pila.pop(); pops += 1
        else:
            pops = len(pila); pila.clear()
        bone['pop_level'] = pops

    result = bytearray()
    for bone in bones_data:
        # Usar bloque original como base si existe
        if 'raw_block' in bone and len(bone['raw_block']) == 0xA0:
            blk = bytearray(bone['raw_block'])
        else:
            blk = bytearray(0xA0)
            # Marker obligatorio en 0x00
            struct.pack_into('<I', blk, 0x00, 0xA0)
            p_idx = bone['padre_idx']
            if p_idx is not None and p_idx < len(bones_data):
                padre_bone = bones_data[p_idx]
                if 'raw_block' in padre_bone and len(padre_bone['raw_block']) == 0xA0:
                    blk[0x40:0xA0] = padre_bone['raw_block'][0x40:0xA0]

        nuevo_pop = bone.get('pop_level', 0)
        if 'raw_block' in bone and len(bone['raw_block']) == 0xA0:
            raw_pop = struct.unpack_from('<I', bone['raw_block'], 0x04)[0]
            if raw_pop >= 64 and raw_pop >= nuevo_pop:
                # raw_pop es "vaciar todo"
                struct.pack_into('<I', blk, 0x04, raw_pop)
            else:
                struct.pack_into('<I', blk, 0x04, nuevo_pop)
        else:
            struct.pack_into('<I', blk, 0x04, nuevo_pop)
        blk[0x08] = 0x01
        blk[0x0A] = bone['bone_id'] & 0xFF
        px, py, pz = bone['pos']
        struct.pack_into('<4f', blk, 0x10, px, py, pz, 1.0)

        tiene_raw = 'raw_block' in bone and len(bone.get('raw_block', b'')) == 0xA0
        p = bone['padre_idx']

        if tiene_raw:
            if p is not None and p < len(bones_data):
                ppx, ppy, ppz = bones_data[p]['pos']
                # Comparar pos_padre actual del raw_block con la del padre actual
                raw_pp = struct.unpack_from('<3f', bone['raw_block'], 0x20)
                padre_pos_actual = bones_data[p]['pos']
                if (abs(raw_pp[0]-ppx)>1e-6 or abs(raw_pp[1]-ppy)>1e-6 or abs(raw_pp[2]-ppz)>1e-6):
                    struct.pack_into('<4f', blk, 0x20, ppx, ppy, ppz, 1.0)
                    struct.pack_into('<4f', blk, 0x30, px-ppx, py-ppy, pz-ppz, 1.0)
        else:
            if p is not None and p < len(bones_data):
                ppx, ppy, ppz = bones_data[p]['pos']
                struct.pack_into('<4f', blk, 0x20, ppx, ppy, ppz, 1.0)
                struct.pack_into('<4f', blk, 0x30, px-ppx, py-ppy, pz-ppz, 1.0)
            else:
                # Raíz nueva
                struct.pack_into('<4f', blk, 0x20, 0., 0., 0., 0.)
                struct.pack_into('<4f', blk, 0x30, px, py, pz, 1.0)
        result += blk
    return bytes(result)


def exportar_pmdl_con_huesos(pmdl_bytes: bytearray, bones_data: list) -> bytearray:
    cantidad_orig = struct.unpack_from('<I', pmdl_bytes, 0x08)[0]
    offset        = struct.unpack_from('<I', pmdl_bytes, 0x50)[0]
    nuevo         = reconstruir_bloque_huesos(bones_data)
    tam_orig      = cantidad_orig * 0xA0
    tam_nuevo     = len(bones_data) * 0xA0
    delta         = tam_nuevo - tam_orig

    r = (bytearray(pmdl_bytes[:offset]) + bytearray(nuevo) +
         bytearray(pmdl_bytes[offset + tam_orig:]))

    struct.pack_into('<I', r, 0x08, len(bones_data))

    if delta != 0:
        # Actualizar parts_index_offset (0x60)
        parts_idx_off = struct.unpack_from('<I', r, 0x60)[0]
        if parts_idx_off > offset:
            parts_idx_off += delta
            struct.pack_into('<I', r, 0x60, parts_idx_off)

        # Actualizar offsets individuales de cada parte en la tabla de índices
        part_count = struct.unpack_from('<I', r, 0x5C)[0]
        for i in range(part_count):
            entry_off = parts_idx_off + i * 0x20
            if entry_off + 0x0C > len(r):
                break
            part_off = struct.unpack_from('<I', r, entry_off + 0x04)[0]
            if part_off > offset:
                struct.pack_into('<I', r, entry_off + 0x04, part_off + delta)

    return r

# Ventana principal
class BoneEditor(ctk.CTkToplevel):
    def __init__(self, parent, pmdl_bytes=None, bones_names=None):
        super().__init__(parent)
        self.title("Editor de Huesos"); self.geometry("1100x680"); self.minsize(900, 560)
        self.pmdl_bytes=bytearray(pmdl_bytes) if pmdl_bytes else None
        self.bones_data=[]; self.bones_names=bones_names or {}
        self._history=[]; self._redo_stack=[]; self.has_unsaved=False
        self.on_close_requested = None
        self._build_ui(); self._bind_keys()
        if pmdl_bytes: self.after(100, self._load_from_bytes)

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top=ctk.CTkFrame(self,corner_radius=0,height=46)
        top.grid(row=0,column=0,sticky="ew"); top.grid_propagate(False)
        ctk.CTkButton(top,text="📂 Abrir PMDL",command=self._open_file,
                      width=120,height=32,font=ctk.CTkFont(size=12)
                      ).pack(side="left",padx=10,pady=7)
        ctk.CTkButton(top,text="💾 Guardar cambios",command=self._guardar,
                      width=145,height=32,font=ctk.CTkFont(size=12),
                      fg_color=("#28a745","#1e7e34"),hover_color=("#218838","#155724")
                      ).pack(side="left",padx=4,pady=7)
        ctk.CTkLabel(top,
                     text="Ctrl+Z · Ctrl+Y  ·  Clic: seleccionar · Rueda: zoom · Medio: rotar · Der: pan",
                     font=ctk.CTkFont(size=10),text_color=("gray55","gray55")
                     ).pack(side="left",padx=14)

        # PanedWindow horizontal con sash
        self._paned = tk.PanedWindow(self, orient="horizontal",
                                     sashrelief="flat", sashwidth=6,
                                     bg="#1e1e2e", sashpad=1,
                                     bd=0, opaqueresize=True)
        self._paned.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        # Panel izquierdo: jerarquía
        tree_frame=ctk.CTkFrame(self._paned,corner_radius=6)
        tree_frame.grid_rowconfigure(1,weight=1); tree_frame.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(tree_frame,text="Jerarquía de huesos",
                     font=ctk.CTkFont(size=12,weight="bold")
                     ).grid(row=0,column=0,sticky="w",padx=10,pady=(6,2))
        self.tree=BoneTree(tree_frame,on_bone_selected=self._on_bone_selected,corner_radius=4)
        self.tree.grid(row=1,column=0,sticky="nsew",padx=2,pady=(0,2))
        self._paned.add(tree_frame, minsize=200)
        # Panel central: vista 3D
        vp_frame=ctk.CTkFrame(self._paned,corner_radius=6)
        vp_frame.grid_rowconfigure(0,weight=1); vp_frame.grid_columnconfigure(0,weight=1)
        self.viewport=BoneViewport(vp_frame,on_bone_picked=self._on_bone_picked_3d,
                                   width=360,height=400)
        self.viewport.pack(fill="both",expand=True,padx=2,pady=2)
        self._paned.add(vp_frame, minsize=250)

        # Panel derecho: propiedades
        props_outer=ctk.CTkFrame(self._paned,corner_radius=6)
        props_outer.grid_rowconfigure(0,weight=1); props_outer.grid_columnconfigure(0,weight=1)
        self.props=BonePropertiesPanel(props_outer,on_apply=self._on_prop_action,corner_radius=6)
        self.props.grid(row=0,column=0,sticky="nsew")
        self._paned.add(props_outer, minsize=220)

        # Aplicar posiciones de sash por defecto y enganchar resize
        self.after(80, self._set_default_sash_positions)
        self.after(250, self._micro_rotate_viewport)
        self.bind("<Configure>", self._on_window_resize)
        self._last_win_size = (0, 0)
        self._poll_resize()

    def _set_default_sash_positions(self):
        total = self._paned.winfo_width() or 1100
        s0 = int(total * 0.33)
        s1 = int(total * 0.78)
        self._paned.sash_place(0, s0, 1)
        self._paned.sash_place(1, s1, 1)
        self._sash_ratios = (s0 / total, s1 / total)
        self._paned.bind("<ButtonRelease-1>", self._on_sash_released)

    def _on_sash_released(self, event=None):
        total = self._paned.winfo_width() or 1
        try:
            s0 = self._paned.sash_coord(0)[0]
            s1 = self._paned.sash_coord(1)[0]
        except Exception:
            return
        self._sash_ratios = (s0 / total, s1 / total)
        self._micro_rotate_viewport()


    def _micro_rotate_viewport(self, retries=0):
        """Fuerza un redraw del viewport esperando a que OpenGL esté realmente listo."""
        try:
            vp = self.viewport
            if not getattr(vp, '_gl_ready', False):
                if retries < 60:  # hasta 6 segundos de espera
                    self.after(100, lambda: self._micro_rotate_viewport(retries + 1))
                return
            vp.rotation_y += 0.001
            vp.redraw()
            vp.rotation_y -= 0.001
            vp.redraw()
        except Exception:
            if retries < 60:
                self.after(100, lambda: self._micro_rotate_viewport(retries + 1))

    def _poll_resize(self):
        try:
            w = self.winfo_width()
            h = self.winfo_height()
            prev = self._last_win_size
            if w > 10 and (w, h) != prev:
                self._last_win_size = (w, h)
                if hasattr(self, '_resize_job'):
                    self.after_cancel(self._resize_job)
                self._resize_job = self.after(80, self._apply_proportional_sash)
        except Exception:
            pass
        finally:
            try:
                self._poll_job = self.after(120, self._poll_resize)
            except Exception:
                pass

    def _on_window_resize(self, event=None):
        if event and event.widget is not self:
            return
        w = self.winfo_width()
        h = self.winfo_height()
        prev = getattr(self, '_last_win_size', (0, 0))
        if (w, h) == prev:
            return
        self._last_win_size = (w, h)
        if hasattr(self, '_resize_job'):
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._apply_proportional_sash)

    def _apply_proportional_sash(self):
        ratios = getattr(self, '_sash_ratios', (0.33, 0.78))
        total = self._paned.winfo_width()
        if total < 10:
            return
        s0 = int(total * ratios[0])
        s1 = int(total * ratios[1])
        s0 = max(200, min(s0, total - 470))
        s1 = max(s0 + 250, min(s1, total - 220))
        self._paned.sash_place(0, s0, 1)
        self._paned.sash_place(1, s1, 1)
        self.after(50, self._micro_rotate_viewport)

    def _bind_keys(self):
        self.after(0, lambda: self.protocol("WM_DELETE_WINDOW", self._on_close))
        self.bind_all("<Escape>", lambda e: self._on_close())
        self.bind_all("<Control-z>", lambda e: self._undo())
        self.bind_all("<Control-y>", lambda e: self._redo())

    # Carga
    def _open_file(self):
        path=filedialog.askopenfilename(title="Abrir PMDL",
            filetypes=[("PMDL","*.pmdl"),("PMDF","*.pmdf"),("Todos","*.*")])
        if not path: return
        with open(path,'rb') as f: self.pmdl_bytes=bytearray(f.read())
        self._load_from_bytes()

    def _load_from_bytes(self):
        from app.logic_3d.bones.bones_reader import leer_armature_pmdl, cargar_nombres_huesos
        bones=leer_armature_pmdl(self.pmdl_bytes)
        if not bones:
            messagebox.showwarning("Editor de Huesos","Este PMDL no tiene huesos."); return
        # #6: adjuntar el bloque raw original a cada hueso para preservarlo al exportar
        cantidad = struct.unpack_from('<I', self.pmdl_bytes, 0x08)[0]
        offset   = struct.unpack_from('<I', self.pmdl_bytes, 0x50)[0]
        for i, bone in enumerate(bones):
            start = offset + i * 0xA0
            bone['raw_block'] = bytes(self.pmdl_bytes[start:start+0xA0])
        self.bones_data=bones
        if not self.bones_names: self.bones_names=cargar_nombres_huesos()
        self._history.clear(); self._redo_stack.clear()
        self._refresh()

    def receive_bones(self, bones_data, pmdl_bytes, names):
        self.bones_data=[dict(b) for b in bones_data]
        self.pmdl_bytes=bytearray(pmdl_bytes) if pmdl_bytes else self.pmdl_bytes
        self.bones_names=names or {}
        if self.pmdl_bytes:
            try:
                cantidad = struct.unpack_from('<I', self.pmdl_bytes, 0x08)[0]
                offset   = struct.unpack_from('<I', self.pmdl_bytes, 0x50)[0]
                for i, bone in enumerate(self.bones_data):
                    if 'raw_block' not in bone and i < cantidad:
                        start = offset + i * 0xA0
                        bone['raw_block'] = bytes(self.pmdl_bytes[start:start+0xA0])
            except Exception: pass
        self._refresh()

    def _refresh(self):
        """Recarga completa — carga inicial / undo / redo."""
        self.tree.load(self.bones_data,self.bones_names)
        self.viewport.set_bones(self.bones_data)   # resetea cámara
        self.props.clear()

    # Selección
    def _on_bone_selected(self, bone):
        self.props.load_bone(bone,self.bones_names,self.bones_data)
        self.viewport.highlight(bone['idx'])

    def _on_bone_picked_3d(self, bone_idx):
        """#5: clic en 3D → selecciona en árbol expandiendo si hace falta."""
        if 0 <= bone_idx < len(self.bones_data):
            bone=self.bones_data[bone_idx]
            self.props.load_bone(bone,self.bones_names,self.bones_data)
            self.tree.select_and_reveal(bone_idx)

    # Acciones
    def _on_prop_action(self, bone_idx, value, action="move", tail_pmdl=None):
        if action=="move":
            self._push_history()
            bone=self.bones_data[bone_idx]; bone['pos']=value
            from app.logic_3d.bones.bones_reader import pmdl_a_visor, ESCALA_GLOBAL, OFFSET_Y_GLOBAL, _recalcular_tails
            bx,by,bz=pmdl_a_visor(*value)
            bone['pos_visor']=(bx*ESCALA_GLOBAL,
                               by*ESCALA_GLOBAL + OFFSET_Y_GLOBAL,
                               bz*ESCALA_GLOBAL)
            # Recalcular tails de toda la jerarquía ya que este hueso movió
            _recalcular_tails(self.bones_data)
            self.viewport.update_bones(self.bones_data)
            self.viewport.highlight(bone_idx)
            self.props.load_bone(bone,self.bones_names,self.bones_data)

        elif action=="move_tail":
            pass

        elif action=="add_child":
            self._add_child_with_picker(bone_idx)

        elif action=="confirm_delete":
            bone = self.bones_data[bone_idx]
            has_children = any(b['padre_idx'] == bone_idx for b in self.bones_data)
            bid = bone['bone_id']
            if has_children:
                msg = f"¿Eliminar Hueso {bid:02X} y todos sus hijos?"
            else:
                msg = f"¿Eliminar Hueso {bid:02X}?"
            if messagebox.askyesno("Confirmar", msg):
                self._push_history()
                self._delete_subtree(bone_idx)
                self._reindex()
                self._refresh()

        elif action=="delete":
            self._push_history()
            self._delete_subtree(bone_idx)
            self._reindex()
            self._refresh()

    def _add_child_with_picker(self, parent_idx):
        used={b['bone_id'] for b in self.bones_data}
        if len(used)>=0xFF:
            messagebox.showwarning("Sin IDs","No hay IDs disponibles (00-FE)."); return
        dlg=BonePickerDialog(self,used,self.bones_names)
        self.wait_window(dlg)
        if dlg.result is None: return

        self._push_history()
        new_id=dlg.result
        parent=self.bones_data[parent_idx]
        px,py,pz=parent['pos']
        from app.logic_3d.bones.bones_reader import pmdl_a_visor, ESCALA_GLOBAL, OFFSET_Y_GLOBAL, _recalcular_tails

        # Calcular posición del nuevo hueso continuando la dirección del padre
        import math
        if parent['padre_idx'] is not None:
            grandparent = self.bones_data[parent['padre_idx']]
            gpx,gpy,gpz = grandparent['pos']
            dx,dy,dz = px-gpx, py-gpy, pz-gpz
            length = math.sqrt(dx*dx+dy*dy+dz*dz)
            if length > 0.001:
                nx,ny,nz = px+dx, py+dy, pz+dz
            else:
                nx,ny,nz = px, py+5.0, pz
        else:
            # Usar tail_visor del padre para inferir dirección
            tv = parent.get('tail_visor')
            if tv and tv != parent.get('pos_visor'):
                tx_p = -tv[0]/ESCALA_GLOBAL
                ty_p = -(tv[1]-OFFSET_Y_GLOBAL)/ESCALA_GLOBAL
                tz_p = tv[2]/ESCALA_GLOBAL
                dx,dy,dz = tx_p-px, ty_p-py, tz_p-pz
                nx,ny,nz = px+dx, py+dy, pz+dz
            else:
                nx,ny,nz = px, py+5.0, pz

        bx,by,bz = pmdl_a_visor(nx,ny,nz)
        # tail del nuevo hueso: mismo delta que head→tail del padre
        tail_nx,tail_ny,tail_nz = nx+(nx-px), ny+(ny-py), nz+(nz-pz)
        btx,bty,btz = pmdl_a_visor(tail_nx,tail_ny,tail_nz)

        insert_pos=self._find_insert_position(parent_idx)

        for b in self.bones_data:
            if b['idx']>=insert_pos: b['idx']+=1
            if b['padre_idx'] is not None and b['padre_idx']>=insert_pos: b['padre_idx']+=1
        if parent_idx>=insert_pos: parent_idx+=1

        new_bone={
            'bone_id':new_id,'idx':insert_pos,'padre_idx':parent_idx,
            'pos':(nx,ny,nz),
            'pos_visor':(bx*ESCALA_GLOBAL, by*ESCALA_GLOBAL+OFFSET_Y_GLOBAL, bz*ESCALA_GLOBAL),
            'tail_pmdl':(tail_nx,tail_ny,tail_nz),
            'tail_visor':(btx*ESCALA_GLOBAL, bty*ESCALA_GLOBAL+OFFSET_Y_GLOBAL, btz*ESCALA_GLOBAL),
            'pop_level':0,'tiene_padre':True,
        }
        self.bones_data.insert(insert_pos,new_bone)

        # Recalcular tails de todos los huesos
        _recalcular_tails(self.bones_data)

        self.viewport.update_bones(self.bones_data)
        self.viewport.highlight(insert_pos)

        self.tree.bones_data=self.bones_data
        self.tree.add_node_after(new_bone,parent_idx,self.bones_data)
        self.tree.select_bone(insert_pos)
        self.props.load_bone(new_bone,self.bones_names,self.bones_data)

    def _find_insert_position(self, parent_idx):
        children_of={}
        for b in self.bones_data:
            p=b['padre_idx']
            if p is not None: children_of.setdefault(p,[]).append(b['idx'])

        def last_desc(idx):
            ch=children_of.get(idx,[])
            if not ch: return idx
            last=max(ch,key=lambda c:next(i for i,b in enumerate(self.bones_data) if b['idx']==c))
            return last_desc(last)

        ld=last_desc(parent_idx)
        for i,b in enumerate(self.bones_data):
            if b['idx']==ld: return i+1
        return len(self.bones_data)

    def _delete_subtree(self, idx):
        for c in [b['idx'] for b in self.bones_data if b['padre_idx']==idx]:
            self._delete_subtree(c)
        self.bones_data=[b for b in self.bones_data if b['idx']!=idx]

    def _reindex(self):
        old_to_new={b['idx']:i for i,b in enumerate(self.bones_data)}
        for i,b in enumerate(self.bones_data):
            b['idx']=i
            if b['padre_idx'] is not None: b['padre_idx']=old_to_new.get(b['padre_idx'])

    # Undo/Redo
    def _push_history(self):
        import copy
        self._history.append(copy.deepcopy(self.bones_data))
        self._redo_stack.clear()
        self.has_unsaved = True
        if len(self._history)>50: self._history.pop(0)

    def _undo(self):
        if not self._history: return
        import copy
        self._redo_stack.append(copy.deepcopy(self.bones_data))
        self.bones_data=self._history.pop(); self._refresh()

    def _redo(self):
        if not self._redo_stack: return
        import copy
        self._history.append(copy.deepcopy(self.bones_data))
        self.bones_data=self._redo_stack.pop(); self._refresh()

    # Guardar
    def _guardar(self):
        if not self.pmdl_bytes:
            messagebox.showerror("Error","No hay ningún PMDL cargado."); return
        if not self.bones_data:
            messagebox.showerror("Error","No hay huesos para guardar."); return
        try:
            self.pmdl_bytes=exportar_pmdl_con_huesos(self.pmdl_bytes,self.bones_data)
            self.has_unsaved = False
            messagebox.showinfo("Guardado","Cambios aplicados al PMDL en memoria.")
        except Exception as e: messagebox.showerror("Error",str(e))

    def get_modified_pmdl(self):
        # Devuelve el bytearray con los cambios aplicados, o None si no hay cambios guardados.
        return bytearray(self.pmdl_bytes) if self.pmdl_bytes else None

    def _on_close(self):
        if getattr(self, 'has_unsaved', False):
            if not messagebox.askyesno(
                "Cambios sin guardar",
                "Hay cambios sin guardar.\n\u00bfSalir de todas formas?",
                default="no"
            ):
                return
        if callable(getattr(self, 'on_close_requested', None)):
            self.on_close_requested()
        else:
            self.destroy()