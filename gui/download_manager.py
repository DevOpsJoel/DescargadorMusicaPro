# DescargarMusica/gui/download_manager.py
import threading
import queue
import uuid
import os
from tkinter import filedialog, messagebox
import time 

import customtkinter as ctk
from core.Descargador import descargar_audio, obtener_info_video

class DownloadManager:
    def __init__(self, app_instance, ui_refs, initial_download_folder, calidad_map_ref, calidad_var_ref, status_icons): # <--- Nuevo argumento status_icons
        # ... (asignaciones existentes) ...
        self.app = app_instance
        self.ui = ui_refs
        self.CARPETA_MUSICA_DEFAULT_PARA_DIALOGO = initial_download_folder
        self.opciones_calidad_audio_map = calidad_map_ref
        self.calidad_audio_display_var_ref = calidad_var_ref
        self.cola_descargas_app = queue.Queue()
        self.lista_gui_cola = {} 
        self.hilo_procesador_cola = None
        self.detener_procesador_cola_event = threading.Event()
        self.status_icons = status_icons # <--- Guardar los iconos de estado
        self.colores_estado = { # Sin cambios
            "Pendiente": ("gray55", "gray60"), "Procesando info...": ("#007ACC", "#50AFFF"), 
            "Descargando...": ("#007ACC", "#50AFFF"), "Completado ✓": ("#2B8C2B", "#70C470"),       
            "Error": ("#D32F2F", "#FF6B6B"), "Error Info": ("#D32F2F", "#FF6B6B"),
            "Error General": ("#D32F2F", "#FF6B6B"), "Error: Tipo Inválido": ("#D32F2F", "#FF6B6B")
        }
        self.color_estado_default = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        self.item_cola_fg_color_normal = "transparent" 
        self.item_cola_fg_color_hover = ("gray75", "gray28")
        
    def _mi_progreso_hook(self, d): # Sin cambios
        # ... (código como antes) ...
        pass

    def _actualizar_item_cola_visual(self, item_id, nuevo_titulo=None, nuevo_estado=None, remover=False):
        if item_id in self.lista_gui_cola:
            item_gui = self.lista_gui_cola[item_id]
            if remover:
                # ... (lógica de remover como antes) ...
                if item_gui['frame'] and item_gui['frame'].winfo_exists(): item_gui['frame'].destroy()
                if item_id in self.lista_gui_cola: del self.lista_gui_cola[item_id] 
            else:
                if nuevo_titulo and 'titulo_var' in item_gui:
                    item_gui['titulo_var'].set(nuevo_titulo[:55] + "..." if len(nuevo_titulo) > 55 else nuevo_titulo)
                
                if nuevo_estado and 'status_var' in item_gui:
                    item_gui['status_var'].set(nuevo_estado)
                    # Aplicar color al texto del estado
                    if item_gui.get('status_widget'):
                        color_para_estado = self.colores_estado.get(nuevo_estado)
                        if color_para_estado is None: 
                            if "Error" in nuevo_estado: color_para_estado = self.colores_estado.get("Error", self.color_estado_default)
                            else: color_para_estado = self.color_estado_default
                        item_gui['status_widget'].configure(text_color=color_para_estado)
                    
                    # --- APLICAR ICONO AL ESTADO ---
                    if item_gui.get('status_icon_widget'):
                        icono_para_estado = self.status_icons.get(nuevo_estado)
                        if icono_para_estado is None: # Fallback si el estado exacto no tiene icono
                            if "Error" in nuevo_estado: icono_para_estado = self.status_icons.get("Error")
                            elif "Completado" in nuevo_estado: icono_para_estado = self.status_icons.get("Completado ✓")
                            elif "Descargando" in nuevo_estado: icono_para_estado = self.status_icons.get("Descargando...")
                            elif "Procesando" in nuevo_estado: icono_para_estado = self.status_icons.get("Procesando info...")
                            else: icono_para_estado = self.status_icons.get("Pendiente") # Default a pendiente
                        
                        item_gui['status_icon_widget'].configure(image=icono_para_estado if icono_para_estado else "") # Si el icono es None, no mostrar imagen


    def _add_item_to_gui_cola(self, item_id, titulo_est):
        if not self.ui["frame_elementos_cola"] or not self.ui["frame_elementos_cola"].winfo_exists(): return
        
        item_frame = ctk.CTkFrame(self.ui["frame_elementos_cola"], fg_color=self.item_cola_fg_color_normal, 
                                  border_width=1, border_color=("gray80", "gray28"), corner_radius=6)
        item_frame.pack(fill="x", pady=(3, 3), padx=3)
        item_frame.grid_columnconfigure(0, weight=0)  # Columna para el icono de estado
        item_frame.grid_columnconfigure(1, weight=1)  # Columna del título (se expande)
        item_frame.grid_columnconfigure(2, weight=0)  # Columna del texto de estado (ancho fijo)
        
        titulo_v = ctk.StringVar(value=titulo_est[:50] + "..." if len(titulo_est) > 50 else titulo_est)
        status_v = ctk.StringVar(value="Pendiente")
        
        # --- Icono de Estado ---
        initial_icon = self.status_icons.get("Pendiente")
        status_icon_label = ctk.CTkLabel(item_frame, text="", image=initial_icon, width=20) # Ajustar width si es necesario
        status_icon_label.grid(row=0, column=0, padx=(5,0), pady=5, sticky="w")

        title_label = ctk.CTkLabel(item_frame, textvariable=titulo_v, font=("Arial", 11), anchor="w", wraplength=130) # Ajustar wraplength
        title_label.grid(row=0, column=1, padx=(5,5), pady=5, sticky="w")
        
        status_text_label = ctk.CTkLabel(item_frame, textvariable=status_v, font=("Arial", 9, "italic"), width=90, anchor="e")
        status_text_label.grid(row=0, column=2, padx=(5,8), pady=5, sticky="e")
        status_text_label.configure(text_color=self.colores_estado.get("Pendiente", self.color_estado_default))
        
        self.lista_gui_cola[item_id] = {
            'frame': item_frame, 
            'titulo_var': titulo_v, 
            'status_var': status_v,
            'status_widget': status_text_label, # Referencia al label de texto del estado
            'status_icon_widget': status_icon_label # <--- Guardar la referencia al label del icono
        }

        def _on_item_enter(event, frame=item_frame): # Sin cambios
            if frame.winfo_exists(): frame.configure(fg_color=self.item_cola_fg_color_hover)
        def _on_item_leave(event, frame=item_frame, original_color=self.item_cola_fg_color_normal): # Sin cambios
            if frame.winfo_exists(): frame.configure(fg_color=original_color)
        item_frame.bind("<Enter>", _on_item_enter); item_frame.bind("<Leave>", _on_item_leave)
        title_label.bind("<Enter>", lambda e,f=item_frame: _on_item_enter(e,f)); title_label.bind("<Leave>", lambda e,f=item_frame,oc=self.item_cola_fg_color_normal: _on_item_leave(e,f,oc))
        status_text_label.bind("<Enter>", lambda e,f=item_frame: _on_item_enter(e,f)); status_text_label.bind("<Leave>", lambda e,f=item_frame,oc=self.item_cola_fg_color_normal: _on_item_leave(e,f,oc))
        status_icon_label.bind("<Enter>", lambda e,f=item_frame: _on_item_enter(e,f)); status_icon_label.bind("<Leave>", lambda e,f=item_frame,oc=self.item_cola_fg_color_normal: _on_item_leave(e,f,oc))

    def _hilo_analizar_y_decidir_encolado(self, url_para_analizar): # Sin cambios en su lógica interna
        
        pass

    def _hilo_procesador_cola_principal(self): # Sin cambios en su lógica interna
        
        pass

    def gestionar_nueva_url(self, url_ingresada_original_desde_gui): # Sin cambios
       
        pass

    def _hilo_analizar_y_decidir_encolado(self, url_para_analizar): # Adaptada
        print(f"Analizando: {url_para_analizar}")
        info_contenido = obtener_info_video(url_para_analizar) 
        videos_a_procesar_temporal = []
        titulo_para_dialogo_carpeta = "este ítem"

        if info_contenido.get('tipo') == 'video':
            videos_a_procesar_temporal.append({'webpage_url': info_contenido['webpage_url'], 'titulo_estimado': info_contenido.get('titulo', 'Video')})
            titulo_para_dialogo_carpeta = info_contenido.get('titulo', 'Video')[:30] + "..."
        elif info_contenido.get('tipo') == 'playlist':
            titulo_playlist, cantidad_videos, videos_de_playlist = info_contenido.get('titulo_playlist', 'Playlist'), info_contenido.get('cantidad_videos', 0), info_contenido.get('videos', [])
            if cantidad_videos > 0 and videos_de_playlist:
                respuesta_q = queue.Queue(); self.app.after(0, lambda: respuesta_q.put(messagebox.askyesno("Playlist Detectada", f"URL es playlist:\n'{titulo_playlist}' ({cantidad_videos} videos).\n\n¿Añadir todos a la cola?", icon='question', parent=self.app)))
                try: respuesta_usuario = respuesta_q.get(timeout=120)
                except queue.Empty: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"Timeout para playlist '{titulo_playlist[:20]}'.")); return
                if respuesta_usuario: videos_a_procesar_temporal.extend(videos_de_playlist); titulo_para_dialogo_carpeta = f"{len(videos_a_procesar_temporal)} videos de '{titulo_playlist[:20]}...'"
                else: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"Playlist '{titulo_playlist[:20]}' no añadida." )); return
            else: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"Playlist '{titulo_playlist[:20]}' vacía.")); self.app.after(0, lambda: messagebox.showwarning("Playlist Inválida", f"Playlist '{titulo_playlist}' vacía.", parent=self.app)); return
        elif info_contenido.get('tipo') == 'error': msg_err=info_contenido.get('mensaje','Error.'); self.app.after(0,lambda: self.ui["estado_general_actual_var"].set(f"Error: {msg_err[:50]}")); self.app.after(0,lambda: messagebox.showerror("Error URL",msg_err, parent=self.app)); return
        else: self.app.after(0,lambda: self.ui["estado_general_actual_var"].set(f"Error: Tipo desconocido.")); self.app.after(0,lambda: messagebox.showerror("Error","No se pudo procesar URL.", parent=self.app)); return
        
        if videos_a_procesar_temporal:
            carpeta_q = queue.Queue(); self.app.after(0, lambda: carpeta_q.put(filedialog.askdirectory(title=f"Seleccionar carpeta para: {titulo_para_dialogo_carpeta}", initialdir=self.CARPETA_MUSICA_DEFAULT_PARA_DIALOGO, parent=self.app)))
            try: carpeta_destino_sel = carpeta_q.get(timeout=120)
            except queue.Empty: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set("Selección de carpeta cancelada.")); return
            if not carpeta_destino_sel: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set("No se seleccionó carpeta.")); return
            
            cal_disp = self.calidad_audio_display_var_ref.get() 
            cal_kbps = self.opciones_calidad_audio_map.get(cal_disp, "192")
            items_added_to_queue_count = 0
            for video_data in videos_a_procesar_temporal:
                item_id = str(uuid.uuid4())
                self.cola_descargas_app.put((video_data['webpage_url'], carpeta_destino_sel, cal_kbps, item_id, video_data['titulo_estimado']))
                self.app.after(0, self._add_item_to_gui_cola, item_id, video_data['titulo_estimado']) # Llama al método de la clase
                items_added_to_queue_count +=1
            if items_added_to_queue_count > 0: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"{items_added_to_queue_count} ítem(s) añadidos ({os.path.basename(carpeta_destino_sel)}). ({self.cola_descargas_app.qsize()} total)"))
        
        if not self.cola_descargas_app.empty() and (self.hilo_procesador_cola is None or not self.hilo_procesador_cola.is_alive()):
            self.detener_procesador_cola_event.clear(); self.hilo_procesador_cola = threading.Thread(target=self._hilo_procesador_cola_principal, daemon=True); self.hilo_procesador_cola.start()

    def _hilo_procesador_cola_principal(self): # Adaptada
        item_proc, url_curr, carpeta_curr, calidad_curr, item_id_curr, _ = False, None, None, None, None, None 
        while not self.detener_procesador_cola_event.is_set():
            item_proc, url_curr, carpeta_curr, calidad_curr, item_id_curr, titulo_est_cola = False, None, None, None, None, None
            try:
                url_curr, carpeta_curr, calidad_curr, item_id_curr, titulo_est_cola = self.cola_descargas_app.get(timeout=1); item_proc = True 
                self.app.after(0, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, nuevo_estado="Procesando info..."))
                self.app.after(0, lambda u=url_curr, t_est=titulo_est_cola: self.ui["estado_general_actual_var"].set(f"Info para: {t_est[:30]}... ({self.cola_descargas_app.qsize()} en cola)"))
                self.app.after(0, lambda: self.ui["video_titulo_actual_var"].set("Título: Cargando...")); self.app.after(0, lambda: self.ui["video_duracion_actual_var"].set("Duración: ..."))
                if self.ui["etiqueta_imagen_actual"]: self.app.after(0, lambda: self.ui["etiqueta_imagen_actual"].configure(image=None, text="Cargando miniatura...")); setattr(self.ui["etiqueta_imagen_actual"], 'image_ref', None)
                if self.ui["frame_estado_y_acciones_actual"] and self.ui["estado_label_actual_widget"]: 
                    self.app.after(0, lambda: self.ui["barra_progreso_actual"].set(0))
                    self.app.after(0, lambda: self.ui["barra_progreso_actual"].pack(in_=self.ui["frame_estado_y_acciones_actual"], pady=(0,5), padx=0, fill="x", before=self.ui["estado_label_actual_widget"]))
                
                info_vid = obtener_info_video(url_curr) 
                if info_vid.get('tipo') == 'video':
                    titulo, duracion, thumb_url, dl_url = info_vid.get('titulo','?'), info_vid.get('duracion','?'), info_vid.get('thumbnail'), info_vid.get('webpage_url', url_curr)
                    self.app.after(0, lambda id=item_id_curr, t=titulo: self._actualizar_item_cola_visual(id, nuevo_titulo=t, nuevo_estado="Descargando..."))
                    self.app.after(0, lambda t=titulo: self.ui["video_titulo_actual_var"].set(f"Título: {t}")); self.app.after(0, lambda d=duracion: self.ui["video_duracion_actual_var"].set(f"Duración: {d}"))
                    if thumb_url: self.app.cargar_imagen_para_gui(thumb_url, self.ui["etiqueta_imagen_actual"]) # Llama al método de app
                    else: 
                        if self.ui["etiqueta_imagen_actual"]: self.app.after(0, lambda: self.ui["etiqueta_imagen_actual"].configure(image=None, text="Miniatura no disponible"))
                    self.app.after(0, lambda t=titulo: self.ui["estado_general_actual_var"].set(f"Descargando: {t[:35]}... ({self.cola_descargas_app.qsize()} en cola)"))
                    descargar_audio(dl_url, carpeta_curr, progreso_hook=self._mi_progreso_hook, calidad_audio_kbps=calidad_curr)
                    self.app.after(0, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, nuevo_estado="Completado ✓"))
                    self.app.after(0, lambda t=titulo: self.ui["estado_general_actual_var"].set(f"Descarga completa: {t[:35]}. ({self.cola_descargas_app.qsize()} en cola)"))
                    self.app.after(2000, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, remover=True))
                    if self.cola_descargas_app.empty(): self.app.after(0, lambda t=titulo, c=carpeta_curr: messagebox.showinfo("Descargas Finalizadas", f"Última descarga: '{t}' en:\n{c}\n\n¡Cola procesada!", parent=self.app))
                elif info_vid.get('tipo') == 'error':
                    msg_err = info_vid.get('mensaje','?'); self.app.after(0, lambda id=item_id_curr, me=msg_err: self._actualizar_item_cola_visual(id, nuevo_estado=f"Error Info: {me[:25]}"))
                    self.app.after(0, lambda m=msg_err,u=url_curr: self.ui["estado_general_actual_var"].set(f"Error info '{u[:20]}': {m[:25]}. Saltando."))
                    self.app.after(0, lambda u=url_curr,m=msg_err: messagebox.showerror("Error Video", f"No info para:\n{u}\nError: {m}", parent=self.app))
                else: 
                    self.app.after(0, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, nuevo_estado="Error: Tipo Inválido"))
                    self.app.after(0, lambda u=url_curr: self.ui["estado_general_actual_var"].set(f"Error: URL '{u[:20]}' no es video. Saltando."))
            except queue.Empty:
                item_proc = False 
                if self.cola_descargas_app.empty(): 
                    self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"Cola vacía."))
                    if self.ui["barra_progreso_actual"].winfo_ismapped(): self.app.after(0, lambda: self.ui["barra_progreso_actual"].pack_forget())
                continue 
            except Exception as e:
                url_prob = locals().get('url_curr', "URL ?"); print(f"Error procesando {url_prob}: {e}"); import traceback; traceback.print_exc()
                self.app.after(0, lambda u=url_prob, err=str(e): self.ui["estado_general_actual_var"].set(f"Error con {u[:30]}: {err[:30]}."))
                if item_id_curr: self.app.after(0, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, nuevo_estado="Error General"))
            finally:
                if item_proc: self.cola_descargas_app.task_done() 
                if self.cola_descargas_app.empty() or item_proc : 
                    if self.ui["barra_progreso_actual"].winfo_ismapped() and (self.cola_descargas_app.empty() or not item_proc) :
                        self.app.after(0, lambda: self.ui["barra_progreso_actual"].pack_forget())
    
    def gestionar_nueva_url(self, url_ingresada_original_desde_gui): # Adaptada
        if not url_ingresada_original_desde_gui:
            messagebox.showerror("Entrada Vacía", "Ingrese URL.", parent=self.app)
            return
        self.ui["estado_general_actual_var"].set(f"Analizando URL: {url_ingresada_original_desde_gui[:40]}...")
        self.app.update_idletasks()
        self.ui["entrada_url_widget"].delete(0, "end") 
        
        threading.Thread(target=self._hilo_analizar_y_decidir_encolado, args=(url_ingresada_original_desde_gui,), daemon=True).start()