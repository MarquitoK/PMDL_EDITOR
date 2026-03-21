import time
import traceback
import customtkinter as ctk
import os
import winsound
from tkinter import filedialog
from threading import Thread, Event
from queue import Queue
from app.binary_builder.mesh_binary_builder import MeshBinaryBuilder
from app.utils.ui_error_window import error_window_ui
from app.utils.window import center_to_window
from app.utils.lang import t


# ===============================
# Clase que procesa en segundo hilo
# ===============================
class ProcesadorPartes:

    def __init__(self, rutas, queue, stop_event):
        self.rutas = rutas
        self.queue = queue
        self.stop_event = stop_event

    def ejecutar(self):
        for ruta in self.rutas:

            if self.stop_event.is_set():
                self.queue.put(("CANCELADO", None))
                return

            nombre = os.path.basename(ruta)

            self.queue.put(("PROCESANDO", nombre))

            try:
                time.sleep(1)
                mesh = MeshBinaryBuilder()
                mesh.make_part(ruta, 80)

                self.queue.put(("FINALIZADO", nombre))

            except Exception as e:
                error_trace = traceback.format_exc()
                self.queue.put(("ERROR", error_trace))
                return

        self.queue.put(("DONE", None))


# ===============================
# UI Principal
# ===============================
class AppPortador:

    @error_window_ui
    def __init__(self, parent):
        self.parent = parent

        rutas = filedialog.askopenfilenames(
            parent=self.parent,
            title=t("port_ttt.titulo_choose"),
            filetypes=[(t("port_ttt.file_json"), "*.json"), (t("port_ttt.all_files"), "*.*")]
        )

        if not rutas:
            return

        self.queue = Queue()
        self.stop_event = Event()

        # ctk.set_appearance_mode("dark")
        # ctk.set_default_color_theme("blue")

        self.root = ctk.CTkToplevel(self.parent)
        self.root.geometry("552x205")
        self.root.title(t("port_ttt.titulo"))

        self.root.transient(self.parent)  # encima de la principal
        self.root.grab_set()  # modal (bloquea la principal)
        center_to_window(self.root, self.parent)

        self.label_archivo = ctk.CTkLabel(
            self.root,
            text="Iniciando..."
        )
        self.label_archivo.pack(pady=15)

        self.label_estado = ctk.CTkLabel(
            self.root,
            text=""
        )
        self.label_estado.pack(pady=10)

        self.btn_cancelar = ctk.CTkButton(
            self.root,
            text=t("port_ttt.btn_cancelar"),
            command=self.cancelar_proceso,
            fg_color="#8B0000",
            hover_color="#550000"
        )
        self.btn_cancelar.pack(pady=10)

        self.procesador = ProcesadorPartes(
            rutas,
            self.queue,
            self.stop_event
        )

        self.hilo = Thread(
            target=self.procesador.ejecutar,
            daemon=True
        )
        self.hilo.start()

        self.verificar_cola()

        self.root.mainloop()

    # ---------------------------------

    def cancelar_proceso(self):
        self.stop_event.set()
        self.btn_cancelar.configure(state="disabled")

    # ---------------------------------

    def verificar_cola(self):

        try:
            while True:
                tipo, mensaje = self.queue.get_nowait()

                if tipo == "PROCESANDO":
                    self.label_archivo.configure(
                        text=t("port_ttt.process", mesg=mensaje)
                    )
                    self.label_estado.configure(text="")

                elif tipo == "FINALIZADO":
                    self.label_estado.configure(
                        text=t("port_ttt.port_part")
                    )

                elif tipo == "DONE":
                    self.label_archivo.configure(
                        text=t("port_ttt.process_succ")
                    )
                    self.label_estado.configure(text="")
                    self.btn_cancelar.configure(state="disabled")
                    winsound.MessageBeep(-1)
                    self.parent.status_var.set(t("port_ttt.statust_ok"))
                    self.root.destroy()
                    return

                elif tipo == "CANCELADO":
                    self.label_archivo.configure(
                        text=t("port_ttt.proces_cancelado")
                    )
                    self.label_estado.configure(text="")
                    self.parent.status_var.set(t("port_ttt.status_cancel"))
                    self.root.destroy()
                    return

                elif tipo == "ERROR":
                    ultimo = mensaje.strip().splitlines()[-1]
                    self.label_archivo.configure(
                        text=t("port_ttt.error_process")
                    )
                    self.label_estado.configure(
                        text=f"{ultimo}"
                    )
                    print(mensaje)
                    self.btn_cancelar.configure(state="disabled")
                    winsound.MessageBeep(-1)
                    self.parent.status_var.set(t("port_ttt.status_error"))
                    return


        except:
            pass

        self.root.after(100, self.verificar_cola)
