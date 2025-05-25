# DescargarMusica/gui/download_manager.py
import threading
import queue
import uuid
import os
from tkinter import filedialog, messagebox
import time 

import customtkinter as ctk
from core.Descargador import procesar_y_descargar_item, obtener_info_video 

class DownloadManager:
    def __init__(self, app_instance, ui_refs, initial_download_folder, 
                 calidad_map_ref, calidad_var_ref, status_icons, 
                 tipo_descarga_var_ref):
        self.app = app_instance
        self.ui = ui_refs
        
        self.CARPETA_MUSICA_DEFAULT_PARA_DIALOGO = initial_download_folder
        self.opciones_calidad_audio_map = calidad_map_ref
        self.calidad_audio_display_var_ref = calidad_var_ref
        self.status_icons = status_icons
        self.tipo_descarga_var_ref = tipo_descarga_var_ref

        self.cola_descargas_app = queue.Queue()
        self.lista_gui_cola = {} 
        self.hilo_procesador_cola = None
        self.detener_procesador_cola_event = threading.Event()

        self.colores_estado = {
            "Pendiente": ("gray55", "gray60"), "Procesando info...": ("#007ACC", "#50AFFF"), 
            "Descargando...": ("#007ACC", "#50AFFF"), "Completado ✓": ("#2B8C2B", "#70C470"),       
            "Error": ("#D32F2F", "#FF6B6B"), "Error Info": ("#D32F2F", "#FF6B6B"),
            "Error General": ("#D32F2F", "#FF6B6B"), "Error: Tipo Inválido": ("#D32F2F", "#FF6B6B")
        }
        try: self.color_estado_default = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        except: self.color_estado_default = ("black", "white")
        self.item_cola_fg_color_normal = "transparent" 
        self.item_cola_fg_color_hover = ("gray75", "gray28")
        
    def _mi_progreso_hook(self, d):
        nombre_archivo_actual = d.get('filename', '').split(os.sep)[-1]
        if d['status'] == 'downloading':
            total_bytes, descargado_bytes = d.get('total_bytes') or d.get('total_bytes_estimate'), d.get('downloaded_bytes', 0)
            progreso_float = descargado_bytes / total_bytes if total_bytes and descargado_bytes is not None and total_bytes > 0 else 0
            porcentaje_str, velocidad_str, eta_str = d.get('_percent_str', f"{progreso_float*100:.1f}%"), d.get('_speed_str', '- B/s'), d.get('_eta_str', '-:--')
            if self.ui["barra_progreso_actual"].winfo_exists(): self.app.after(0, lambda: self.ui["barra_progreso_actual"].set(progreso_float if 0 <= progreso_float <= 1 else 0))
            if self.ui["estado_general_actual_var"]: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(
                f"Descargando '{nombre_archivo_actual[:20]}...': {porcentaje_str.strip()} | {velocidad_str.strip()} | ETA: {eta_str.strip()} ({self.cola_descargas_app.qsize()} en cola)" ))
        elif d['status'] == 'finished':
            if self.ui["barra_progreso_actual"].winfo_exists(): self.app.after(0, lambda: self.ui["barra_progreso_actual"].set(1))
            if self.ui["estado_general_actual_var"]: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"Completado: '{nombre_archivo_actual[:30]}...'. Procesando... ({self.cola_descargas_app.qsize()} en cola)"))
        elif d['status'] == 'error':
            if self.ui["estado_general_actual_var"]: self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"Error descargando '{nombre_archivo_actual[:30]}...' ({self.cola_descargas_app.qsize()} en cola)"))

    def _actualizar_item_cola_visual(self, item_id, nuevo_titulo=None, nuevo_estado=None, remover=False):
        if item_id in self.lista_gui_cola:
            item_gui = self.lista_gui_cola[item_id]
            if remover:
                if item_gui['frame'] and item_gui['frame'].winfo_exists(): item_gui['frame'].destroy()
                if item_id in self.lista_gui_cola: del self.lista_gui_cola[item_id] 
            else:
                if nuevo_titulo and 'titulo_var' in item_gui and item_gui['titulo_var'].get() != nuevo_titulo:
                    item_gui['titulo_var'].set(nuevo_titulo[:55] + "..." if len(nuevo_titulo) > 55 else nuevo_titulo)
                if nuevo_estado and 'status_var' in item_gui and item_gui['status_var'].get() != nuevo_estado:
                    item_gui['status_var'].set(nuevo_estado)
                    if item_gui.get('status_widget') and item_gui['status_widget'].winfo_exists():
                        color_para_estado = self.colores_estado.get(nuevo_estado)
                        if color_para_estado is None: 
                            if "Error" in nuevo_estado: color_para_estado = self.colores_estado.get("Error", self.color_estado_default)
                            else: color_para_estado = self.color_estado_default
                        item_gui['status_widget'].configure(text_color=color_para_estado)
                    if item_gui.get('status_icon_widget') and item_gui['status_icon_widget'].winfo_exists():
                        icono_para_estado = self.status_icons.get(nuevo_estado)
                        if icono_para_estado is None: 
                            if "Error" in nuevo_estado: icono_para_estado = self.status_icons.get("Error")
                            elif "Completado" in nuevo_estado: icono_para_estado = self.status_icons.get("Completado ✓")
                            elif "Descargando" in nuevo_estado: icono_para_estado = self.status_icons.get("Descargando...")
                            elif "Procesando" in nuevo_estado: icono_para_estado = self.status_icons.get("Procesando info...")
                            else: icono_para_estado = self.status_icons.get("Pendiente")
                        item_gui['status_icon_widget'].configure(image=icono_para_estado if icono_para_estado else "")

    def _add_item_to_gui_cola(self, item_id, titulo_est):
        if not self.ui["frame_elementos_cola"] or not self.ui["frame_elementos_cola"].winfo_exists(): return
        item_frame = ctk.CTkFrame(self.ui["frame_elementos_cola"], fg_color=self.item_cola_fg_color_normal, border_width=1, border_color=("gray80", "gray28"), corner_radius=6); item_frame.pack(fill="x", pady=(3, 3), padx=3)
        item_frame.grid_columnconfigure(0, weight=0); item_frame.grid_columnconfigure(1, weight=1); item_frame.grid_columnconfigure(2, weight=0)  
        titulo_v = ctk.StringVar(value=titulo_est[:50] + "..." if len(titulo_est) > 50 else titulo_est); status_v = ctk.StringVar(value="Pendiente")
        initial_icon = self.status_icons.get("Pendiente") if self.status_icons else None
        status_icon_label = ctk.CTkLabel(item_frame, text="", image=initial_icon, width=20); status_icon_label.grid(row=0, column=0, padx=(5,0), pady=5, sticky="w")
        title_label = ctk.CTkLabel(item_frame, textvariable=titulo_v, font=("Arial", 11), anchor="w", wraplength=130); title_label.grid(row=0, column=1, padx=(5,5), pady=5, sticky="w")
        status_text_label = ctk.CTkLabel(item_frame, textvariable=status_v, font=("Arial", 9, "italic"), width=90, anchor="e"); status_text_label.grid(row=0, column=2, padx=(5,8), pady=5, sticky="e")
        status_text_label.configure(text_color=self.colores_estado.get("Pendiente", self.color_estado_default))
        self.lista_gui_cola[item_id] = {'frame': item_frame, 'titulo_var': titulo_v, 'status_var': status_v, 'status_widget': status_text_label, 'status_icon_widget': status_icon_label}
        def _on_enter(e,f=item_frame): f.configure(fg_color=self.item_cola_fg_color_hover) if f.winfo_exists() else None
        def _on_leave(e,f=item_frame,oc=self.item_cola_fg_color_normal): f.configure(fg_color=oc) if f.winfo_exists() else None
        for w in [item_frame, title_label, status_text_label, status_icon_label]: w.bind("<Enter>",_on_enter); w.bind("<Leave>",_on_leave)

    def _hilo_analizar_y_decidir_encolado(self, url_para_analizar):
        info_contenido = obtener_info_video(url_para_analizar) 
        videos_a_procesar_temporal = []; titulo_para_dialogo_carpeta = "este ítem"
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
            cal_disp = self.calidad_audio_display_var_ref.get(); cal_kbps = self.opciones_calidad_audio_map.get(cal_disp, "192")
            tipo_descarga_seleccionado = self.tipo_descarga_var_ref.get()
            items_added_to_queue_count = 0
            for video_data in videos_a_procesar_temporal:
                item_id = str(uuid.uuid4())
                self.cola_descargas_app.put((video_data['webpage_url'], carpeta_destino_sel, cal_kbps if tipo_descarga_seleccionado == "audio" else "N/A", tipo_descarga_seleccionado, item_id, video_data['titulo_estimado']))
                self.app.after(0, self._add_item_to_gui_cola, item_id, video_data['titulo_estimado'])
                items_added_to_queue_count +=1
            if items_added_to_queue_count > 0: desc_tipo_str = "Video(s)" if tipo_descarga_seleccionado == "video" else "Audio(s)"; self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(f"{items_added_to_queue_count} {desc_tipo_str} añadidos ({os.path.basename(carpeta_destino_sel)}). ({self.cola_descargas_app.qsize()} total)"))
        
        if not self.cola_descargas_app.empty() and (self.hilo_procesador_cola is None or not self.hilo_procesador_cola.is_alive()):
            self.detener_procesador_cola_event.clear(); self.hilo_procesador_cola = threading.Thread(target=self._hilo_procesador_cola_principal, daemon=True); self.hilo_procesador_cola.start()

    def _hilo_procesador_cola_principal(self):
        while not self.detener_procesador_cola_event.is_set():
            url_curr, carpeta_curr, calidad_curr, tipo_descarga_item, item_id_curr, titulo_est_cola = None, None, None, None, None, None
            item_proc = False
            try:
                url_curr, carpeta_curr, calidad_curr, tipo_descarga_item, item_id_curr, titulo_est_cola = self.cola_descargas_app.get(timeout=1); item_proc = True 
                self.app.after(0, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, nuevo_estado="Procesando info..."))
                self.app.after(0, lambda t_est=titulo_est_cola: self.ui["estado_general_actual_var"].set(f"Info para: {t_est[:30]}... ({self.cola_descargas_app.qsize()} en cola)"))
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
                    if thumb_url: self.app.cargar_imagen_para_gui(thumb_url, self.ui["etiqueta_imagen_actual"])
                    else: 
                        if self.ui["etiqueta_imagen_actual"]: self.app.after(0, lambda: self.ui["etiqueta_imagen_actual"].configure(image=None, text="Miniatura no disponible"))
                    self.app.after(0, lambda t=titulo: self.ui["estado_general_actual_var"].set(f"Descargando: {t[:35]}... ({self.cola_descargas_app.qsize()} en cola)"))
                    procesar_y_descargar_item(dl_url, carpeta_curr, progreso_hook=self._mi_progreso_hook, calidad_audio_kbps=calidad_curr, tipo_descarga=tipo_descarga_item)
                    self.app.after(0, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, nuevo_estado="Completado ✓"))
                    self.app.after(0, lambda t=titulo: self.ui["estado_general_actual_var"].set(f"Descarga completa: {t[:35]}. ({self.cola_descargas_app.qsize()} en cola)"))
                    self.app.after(2000, lambda id=item_id_curr: self._actualizar_item_cola_visual(id, remover=True))
                    if self.cola_descargas_app.empty(): self.app.after(0, lambda t=titulo, c=carpeta_curr: messagebox.showinfo("Descargas Finalizadas", f"Última descarga: '{t}' en:\n{c}\n\n¡Cola procesada!", parent=self.app))
                elif info_vid.get('tipo') == 'error':
                    msg_err = info_vid.get('mensaje','?'); self.app.after(0, lambda id=item_id_curr, me=msg_err: self._actualizar_item_cola_visual(id, nuevo_estado=f"Error Info: {me[:25]}"))
                    self.app.after(0, lambda m=msg_err,u=url_curr: self.ui["estado_general_actual_var"].set(f"Error info '{u[:20]}': {m[:25]}. Saltando."))
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
    
    def gestionar_nueva_url(self, url_ingresada_original_desde_gui):
        if not url_ingresada_original_desde_gui: messagebox.showerror("Entrada Vacía", "Ingrese URL.", parent=self.app); return
        self.ui["estado_general_actual_var"].set(f"Analizando URL: {url_ingresada_original_desde_gui[:40]}...")
        self.app.update_idletasks(); self.ui["entrada_url_widget"].delete(0, "end") 
        threading.Thread(target=self._hilo_analizar_y_decidir_encolado, args=(url_ingresada_original_desde_gui,), daemon=True).start()

    def limpiar_cola_pendientes_async(self):
        self.ui["estado_general_actual_var"].set("Limpiando ítems pendientes...")
        # El trabajo real se hace en el hilo _hilo_limpiar_cola_pendientes
        threading.Thread(target=self._hilo_limpiar_cola_pendientes, daemon=True).start()

    def _hilo_limpiar_cola_pendientes(self):
        print("DEBUG: Hilo Limpiar Pendientes iniciado.")
        # Paso 1: Identificar los item_ids de la GUI que están "Pendiente"
        # Esta operación es segura para leer desde el hilo porque solo accede a StringVars
        # y el diccionario lista_gui_cola. Si hubiera preocupación por modificar lista_gui_cola
        # concurrentemente, se necesitaría un lock para esta lectura.
        ids_gui_pendientes_a_remover = []
        # Hacemos una copia de las claves para iterar de forma segura, ya que _actualizar_item_cola_visual puede modificar el dict
        for item_id_loop, data_loop in list(self.lista_gui_cola.items()): 
            # Acceder a StringVar.get() desde un hilo secundario ES PROBLEMÁTICO.
            # Debemos pasar esta lógica al hilo principal o pasar los estados al hilo secundario.
            # Por ahora, asumiremos que esta es la causa del problema.
            # La solución es obtener los estados en el hilo principal ANTES de llamar a este hilo.
            # PERO, limpiar_cola_pendientes_async ya está en el hilo principal cuando identifica
            # y remueve los frames. _hilo_filtrar_cola_interna es el que limpia la cola de datos.
            
            # REVISIÓN DE LÓGICA: limpiar_cola_pendientes_async debe identificar y remover de GUI.
            # _hilo_filtrar_cola_interna solo debe limpiar self.cola_descargas_app
            # usando los IDs que se le pasen.
            pass # Esta función se rehará.

        # ----- NUEVA LÓGICA PARA _hilo_limpiar_cola_pendientes y su llamador -----
        # Esta función será llamada por limpiar_cola_pendientes_async y recibirá los IDs a remover de la cola interna
    
    def _hilo_filtrar_cola_interna(self, ids_gui_ya_removidos):
        print(f"DEBUG: Hilo de filtrado de cola interna iniciado. IDs a verificar para remover: {ids_gui_ya_removidos}")
        items_a_reencolar = []
        items_removidos_de_cola = 0
        
        # Vaciar la cola de forma segura
        # No se necesita lock aquí si se usa get_nowait en un bucle
        # y se reconstruye. queue.Queue es thread-safe para sus operaciones.
        temp_list_from_queue = []
        while not self.cola_descargas_app.empty():
            try:
                temp_list_from_queue.append(self.cola_descargas_app.get_nowait())
            except queue.Empty:
                break
        
        for item_tupla in temp_list_from_queue:
            # item_tupla: (url, destino, calidad, tipo_descarga, item_id, titulo_estimado)
            item_id_en_tupla = item_tupla[4] # item_id es el 5to elemento, índice 4
            
            if item_id_en_tupla in ids_gui_ya_removidos:
                # Este ítem fue identificado como "Pendiente" en la GUI y ya se eliminó visualmente.
                # Ahora lo eliminamos de la cola interna.
                items_removidos_de_cola += 1
                print(f"DEBUG: Ítem ID {item_id_en_tupla} descartado de la cola interna.")
                try:
                    # Es importante llamar a task_done() para cada get() que no resulte en un put()
                    # o que no sea procesado por el hilo principal de descargas.
                    self.cola_descargas_app.task_done() 
                except ValueError: # Si se llama demasiadas veces
                    pass # Puede ocurrir si el item fue procesado y task_done llamado justo antes
            else:
                # Este ítem no estaba en la lista de pendientes de la GUI (o no era pendiente), se mantiene.
                items_a_reencolar.append(item_tupla)
        
        # Re-poblar la cola con los ítems no eliminados
        for item in items_a_reencolar:
            self.cola_descargas_app.put(item)

        print(f"DEBUG: Hilo de filtrado finalizado. {items_removidos_de_cola} ítems eliminados de la cola interna.")
        self.app.after(0, lambda: self.ui["estado_general_actual_var"].set(
            f"Limpieza de pendientes finalizada. ({self.cola_descargas_app.qsize()} ítems restantes en cola)"
        ))

    def limpiar_cola_pendientes_async(self): # Esta se llama desde el HILO PRINCIPAL (botón)
        print("DEBUG: Botón Limpiar Pendientes presionado.")
        
        ids_gui_pendientes_a_remover = []
        # Iterar sobre una copia para poder modificar el diccionario de forma segura si es necesario
        for item_id, data in list(self.lista_gui_cola.items()):
            if data['status_var'].get() == "Pendiente": # .get() en StringVar es seguro en hilo principal
                ids_gui_pendientes_a_remover.append(item_id)
        
        if not ids_gui_pendientes_a_remover:
            self.ui["estado_general_actual_var"].set("No hay ítems 'Pendiente' para eliminar.")
            print("DEBUG: No se encontraron ítems visuales 'Pendiente'.")
            return

        num_a_remover = len(ids_gui_pendientes_a_remover)
        self.ui["estado_general_actual_var"].set(f"Eliminando {num_a_remover} ítem(s) 'Pendiente'...")
        
        # Eliminar de la GUI por lotes (esto ya no debería congelar)
        self._remover_gui_en_lotes(ids_gui_pendientes_a_remover.copy()) # Pasar una copia

        # Lanzar hilo para limpiar la cola interna
        threading.Thread(target=self._hilo_filtrar_cola_interna, args=(ids_gui_pendientes_a_remover,), daemon=True).start()

    def _remover_gui_en_lotes(self, lista_ids_a_remover_gui, tamano_lote=5):
        # Esta función se ejecuta en el hilo principal a través de app.after
        lote_actual = lista_ids_a_remover_gui[:tamano_lote]
        lista_restante = lista_ids_a_remover_gui[tamano_lote:]

        for item_id in lote_actual:
            # _actualizar_item_cola_visual se encarga de destruir el frame y borrar de self.lista_gui_cola
            self._actualizar_item_cola_visual(item_id, remover=True) 
            print(f"DEBUG: Ítem GUI {item_id} removido visualmente (lote).")

        if lista_restante:
            self.app.after(10, self._remover_gui_en_lotes, lista_restante, tamano_lote)
        else:
            print("DEBUG: Destrucción visual por lotes completada.")
            # El mensaje final de estado se actualiza en _hilo_filtrar_cola_interna
            # para reflejar el estado real de la cola interna.