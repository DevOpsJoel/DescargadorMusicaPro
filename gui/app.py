# DescargarMusica/gui/app.py
import sys
import os
import platform 
import subprocess 
# json no se usa aquí directamente para config
from tkinter import filedialog, messagebox 
import time 
import uuid 
import threading
import queue # Solo para las colas internas de respuesta de messagebox
import urllib.request, urllib.error 
from io import BytesIO

import customtkinter as ctk
from PIL import Image
# appdirs se usa en config_utils

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.config_utils import (
    resource_path_gui, APP_NAME, CARPETA_MUSICA, config_app_actual,
    cargar_configuracion_inicial, guardar_configuracion_actual,
    CONFIG_DEFAULTS, APP_VERSION, # Importar APP_VERSION
    verificar_actualizaciones_en_hilo # <--- FUNCIÓN DE ACTUALIZACIÓN IMPORTADA
)
from gui.download_manager import DownloadManager
# core.Descargador se importa dentro de DownloadManager

cargar_configuracion_inicial() 

app = ctk.CTk()
app.title(f"{APP_NAME} v{APP_VERSION}") # Mostrar versión en el título de la ventana
app.geometry("850x700") 
app.minsize(600, 700) 

app.grid_columnconfigure(0, weight=0, minsize=300); app.grid_columnconfigure(1, weight=1)          
app.grid_rowconfigure(0, weight=1); app.grid_rowconfigure(1, weight=0)             

img_add_queue, img_open_folder, img_settings = None, None, None
img_status_pending, img_status_processing, img_status_downloading, \
img_status_completed, img_status_error = None, None, None, None, None
try:
    icon_map={"add":"add_icon.png","folder":"folder_icon.png","settings":"settings_icon.png","s_pending":"status_pending.png","s_processing":"status_processing.png","s_downloading":"status_downloading.png","s_completed":"status_completed.png","s_error":"status_error.png"}
    loaded_images={}
    for k,fn in icon_map.items():
        p=resource_path_gui(os.path.join('assets','icons',fn))
        if os.path.exists(p):loaded_images[k]=ctk.CTkImage(Image.open(p),size=((18,18) if k.startswith("s_") else (20,20)))
        else:print(f"Icono no encontrado: {p}")
    img_add_queue,img_open_folder,img_settings=loaded_images.get("add"),loaded_images.get("folder"),loaded_images.get("settings")
    img_status_pending,img_status_processing,img_status_downloading,img_status_completed,img_status_error=loaded_images.get("s_pending"),loaded_images.get("s_processing",img_status_pending),loaded_images.get("s_downloading"),loaded_images.get("s_completed"),loaded_images.get("s_error")
except Exception as e:print(f"Error cargando iconos: {e}")

status_icons_map = {"Pendiente": img_status_pending, "Procesando info...": img_status_processing, "Descargando...": img_status_downloading, "Completado ✓": img_status_completed, "Error": img_status_error, "Error Info": img_status_error, "Error General": img_status_error, "Error: Tipo Inválido": img_status_error}
estado_general_actual_var = ctk.StringVar(value="Ingrese URL para añadir a cola"); video_titulo_actual_var = ctk.StringVar(value="Título: -"); video_duracion_actual_var = ctk.StringVar(value="Duración: -")
opciones_calidad_audio_map_app = {"128 kbps (Estándar)":"128","192 kbps (Buena)":"192","256 kbps (Alta)":"256","320 kbps (Máxima)":"320"}; calidad_audio_display_var_app = ctk.StringVar(value=list(opciones_calidad_audio_map_app.keys())[1])
tipo_descarga_switch_var = ctk.StringVar(value="audio") 
info_carpeta_descargas_label = None; etiqueta_imagen_actual = None; frame_estado_y_acciones_actual_dm = None; estado_label_actual_dm = None; entrada_url_dm = None; queue_scrollable_area_dm = None 
barra_progreso_actual = ctk.CTkProgressBar(app, height=15); barra_progreso_actual.set(0)

class ToolTip:
    def __init__(self, widget, text_func, delay=600, **kwargs):
        self.widget, self.text_func, self.delay, self.kwargs = widget, text_func, delay, kwargs
        self.tooltip_window, self.id_after_show, self.id_after_hide = None, None, None
        self.widget.bind("<Enter>", self.on_enter, add="+"); self.widget.bind("<Leave>", self.on_leave, add="+"); self.widget.bind("<ButtonPress>", self.on_leave, add="+") 
    def on_enter(self,e=None): self._cancel_pending_hide(); _ = self.tooltip_window or self.id_after_show and self.widget.after_cancel(self.id_after_show); self.id_after_show=self.widget.after(self.delay,self._show_tooltip_actual)
    def on_leave(self,e=None): self._cancel_pending_show(); self.id_after_hide=self.widget.after(100,self._hide_tooltip_actual) if self.tooltip_window else None
    def _cancel_pending_show(self):
        if self.id_after_show:self.widget.after_cancel(self.id_after_show);self.id_after_show=None
    def _cancel_pending_hide(self):
        if self.id_after_hide:self.widget.after_cancel(self.id_after_hide);self.id_after_hide=None
    def _show_tooltip_actual(self):
        if self.tooltip_window:return
        xr,yr=self.widget.winfo_pointerxy(); wuc=self.widget.winfo_containing(xr,yr)
        if wuc!=self.widget: self._hide_tooltip_actual(); return
        self.tooltip_window=ctk.CTkToplevel(self.widget); self.tooltip_window.wm_overrideredirect(True)
        txt=self.text_func(); fg=self.kwargs.get("fg_color",("#F0F0F0","#2B2B2B")); tc=self.kwargs.get("text_color",("#101010","#DCE4EE")); fnt=self.kwargs.get("font",("Arial",10))
        ctk.CTkLabel(self.tooltip_window,text=txt,fg_color=fg,text_color=tc,corner_radius=4,padx=7,pady=4,font=fnt).pack();self._reposition_tooltip_actual();self.tooltip_window.attributes("-topmost",True)
    def _hide_tooltip_actual(self,e=None):
        self._cancel_pending_show()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
    def _reposition_tooltip_actual(self,e=None):
        if self.tooltip_window:
            x,y=self.widget.winfo_pointerx()+15,self.widget.winfo_pointery()+20;self.tooltip_window.update_idletasks()
            tw,th=self.tooltip_window.winfo_width(),self.tooltip_window.winfo_height();sw,sh=self.widget.winfo_screenwidth(),self.widget.winfo_screenheight()
            if x+tw>sw-10:x=self.widget.winfo_pointerx()-tw-15
            if y+th>sh-10:y=self.widget.winfo_pointery()-th-15
            self.tooltip_window.wm_geometry(f"+{x}+{y}")

def cargar_imagen_para_gui(url_imagen, etiqueta_destino_widget_ref):
    if not url_imagen:
        if etiqueta_destino_widget_ref and etiqueta_destino_widget_ref.winfo_exists(): app.after(0, lambda: (etiqueta_destino_widget_ref.configure(image=None, text="Miniatura no disponible"), setattr(etiqueta_destino_widget_ref, 'image_ref', None)))
        return
    threading.Thread(target=hilo_cargar_imagen_bytes, args=(url_imagen, etiqueta_destino_widget_ref), daemon=True).start()

def hilo_cargar_imagen_bytes(url_imagen, etiqueta_destino_widget_ref):
    try:
        req = urllib.request.Request(url_imagen, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as u: raw_data = u.read()
        if not raw_data:
            if etiqueta_destino_widget_ref and etiqueta_destino_widget_ref.winfo_exists(): app.after(0, lambda: (etiqueta_destino_widget_ref.configure(image=None, text="Miniatura vacía"), setattr(etiqueta_destino_widget_ref, 'image_ref', None) ))
            return
        imagen_pil = Image.open(BytesIO(raw_data))
        try: resample_filter = Image.Resampling.LANCZOS
        except AttributeError: resample_filter = Image.ANTIALIAS 
        target_width = 440 
        if etiqueta_destino_widget_ref and etiqueta_destino_widget_ref.winfo_ismapped() and etiqueta_destino_widget_ref.winfo_width() > 20: target_width = etiqueta_destino_widget_ref.winfo_width()
        img_w, img_h = imagen_pil.size; 
        if img_w == 0: raise ValueError("Img sin dimensiones.")
        new_w, new_h = min(img_w, target_width), int(min(img_w, target_width) * (img_h/img_w))
        if new_h == 0 and new_w > 0 : new_h = int(new_w * 0.5625) 
        elif new_h == 0 and new_w == 0: raise ValueError("Imagen procesada sin dimensiones.")
        imagen_pil = imagen_pil.resize((new_w, new_h), resample_filter)
        img_ctk = ctk.CTkImage(light_image=imagen_pil, dark_image=imagen_pil, size=(new_w, new_h))
        if etiqueta_destino_widget_ref and etiqueta_destino_widget_ref.winfo_exists(): 
            def update_widget():
                if etiqueta_destino_widget_ref.winfo_exists():
                    setattr(etiqueta_destino_widget_ref, 'image_ref', img_ctk) 
                    etiqueta_destino_widget_ref.configure(image=img_ctk, text="")
            app.after(0, update_widget)
    except Exception as e: 
        print(f"Error img ({url_imagen}): {e}")
        if etiqueta_destino_widget_ref and etiqueta_destino_widget_ref.winfo_exists(): app.after(0, lambda: (etiqueta_destino_widget_ref.configure(image=None, text="Error miniatura"), setattr(etiqueta_destino_widget_ref, 'image_ref', None) ))

def abrir_carpeta_descargas_ui_cmd():
    global CARPETA_MUSICA 
    try:
        if platform.system() == "Windows": os.startfile(os.path.realpath(CARPETA_MUSICA))
        elif platform.system() == "Darwin": subprocess.run(["open", CARPETA_MUSICA], check=True)
        else: subprocess.run(["xdg-open", CARPETA_MUSICA], check=True)
    except FileNotFoundError: messagebox.showerror("Error", f"Carpeta no existe: {CARPETA_MUSICA}", parent=app)
    except Exception as e: messagebox.showerror("Error", f"No se pudo abrir carpeta ({CARPETA_MUSICA}):\n{e}", parent=app)
        
def abrir_ventana_configuracion_ui_cmd():
    global CARPETA_MUSICA, config_app_actual, info_carpeta_descargas_label, app, CONFIG_DEFAULTS, download_mgr # Añadir download_mgr
    config_window = ctk.CTkToplevel(app); config_window.title("Configuración"); 
    config_window.geometry("550x380"); # Un poco más alto
    config_window.attributes("-topmost", True); config_window.grab_set()
    temp_dl_var = ctk.StringVar(value=CARPETA_MUSICA); temp_app_mode_var = ctk.StringVar(value=config_app_actual.get("appearance_mode", CONFIG_DEFAULTS["appearance_mode"])); temp_color_theme_var = ctk.StringVar(value=config_app_actual.get("color_theme", CONFIG_DEFAULTS["color_theme"]))
    mf = ctk.CTkFrame(config_window, fg_color="transparent"); mf.pack(padx=20,pady=20,fill="both",expand=True)
    ctk.CTkLabel(mf,text="Carpeta de Descarga Por Defecto:").grid(row=0,column=0,padx=(0,10),pady=10,sticky="w"); ctk.CTkEntry(mf,textvariable=temp_dl_var,width=300).grid(row=0,column=1,padx=0,pady=10,sticky="ew")
    def sel_nva_carp():
        r_sel = filedialog.askdirectory(initialdir=temp_dl_var.get(), parent=config_window)
        if r_sel: temp_dl_var.set(os.path.abspath(r_sel))
    ctk.CTkButton(mf,text="Seleccionar...",command=sel_nva_carp,width=100).grid(row=0,column=2,padx=10,pady=10)
    ctk.CTkLabel(mf,text="Modo de Apariencia:").grid(row=1,column=0,padx=(0,10),pady=10,sticky="w"); app_opts=["Light","Dark","System"]; ctk.CTkComboBox(mf,values=app_opts,variable=temp_app_mode_var,width=150).grid(row=1,column=1,padx=0,pady=10,sticky="w")
    ctk.CTkLabel(mf,text="Tema de Color:").grid(row=2,column=0,padx=(0,10),pady=10,sticky="w"); theme_opts=["blue","green","dark-blue"]; ctk.CTkComboBox(mf,values=theme_opts,variable=temp_color_theme_var,width=150).grid(row=2,column=1,padx=0,pady=10,sticky="w")
    
    # --- SECCIÓN DE ACTUALIZACIÓN EN VENTANA DE CONFIG ---
    version_frame = ctk.CTkFrame(mf, fg_color="transparent")
    version_frame.grid(row=3, column=0, columnspan=3, pady=(15,5), sticky="ew")
    ctk.CTkLabel(version_frame, text=f"Versión actual: {APP_VERSION}", font=("Arial", 10)).pack(side="left", padx=(0,10))
    def comando_verificar_manual():
        if download_mgr and hasattr(download_mgr, 'ui'):
            threading.Thread(target=verificar_actualizaciones_en_hilo, 
                             args=(app, download_mgr.ui, True), # True para es_manual
                             daemon=True).start()
        else: messagebox.showerror("Error", "Download Manager no está listo.", parent=config_window)
    ctk.CTkButton(version_frame, text="Buscar Actualizaciones", command=comando_verificar_manual).pack(side="left")
    # --- FIN SECCIÓN DE ACTUALIZACIÓN ---

    baf = ctk.CTkFrame(mf,fg_color="transparent"); baf.grid(row=5,column=0,columnspan=3,pady=(20,0),sticky="s"); # Fila ajustada
    mf.grid_rowconfigure(4, weight=1); mf.grid_columnconfigure(1,weight=1) # Fila 4 es para empujar
    def guardar_y_aplicar_cambios_config_win():
        global CARPETA_MUSICA,config_app_actual,app 
        n_carp=os.path.abspath(temp_dl_var.get())
        try: os.makedirs(n_carp,exist_ok=True); CARPETA_MUSICA=n_carp; config_app_actual["download_folder"]=CARPETA_MUSICA
        except Exception as e: messagebox.showerror("Error Carpeta",f"No se pudo establecer:\n{n_carp}\nError: {e}",parent=config_window); return
        n_modo=temp_app_mode_var.get()
        if n_modo!=config_app_actual.get("appearance_mode"): ctk.set_appearance_mode(n_modo);config_app_actual["appearance_mode"]=n_modo
        n_tema=temp_color_theme_var.get(); tema_chg=False
        if n_tema!=config_app_actual.get("color_theme"): config_app_actual["color_theme"]=n_tema; tema_chg=True
        if not guardar_configuracion_actual(info_carpeta_descargas_label): messagebox.showerror("Error Guardado", "Configuración no guardada.", parent=config_window)
        if tema_chg: messagebox.showinfo("Reinicio Sugerido","Cambio de tema se aplicará al reiniciar.",parent=config_window)
        config_window.destroy()
    ctk.CTkButton(baf,text="Guardar y Aplicar",command=guardar_y_aplicar_cambios_config_win).pack(side="left",padx=10); ctk.CTkButton(baf,text="Cancelar",command=config_window.destroy).pack(side="left",padx=10); config_window.bind("<Escape>",lambda e:config_window.destroy())

# --- LAYOUT DE LA INTERFAZ GRÁFICA PRINCIPAL (CON SIDEBAR) ---
sidebar_frame = ctk.CTkFrame(app, width=280, corner_radius=0); sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=10); sidebar_frame.grid_rowconfigure(4, weight=1)
frame_titulo_y_config = ctk.CTkFrame(sidebar_frame, fg_color="transparent"); frame_titulo_y_config.grid(row=0, column=0, padx=10, pady=(10,10), sticky="ew")
ctk.CTkLabel(frame_titulo_y_config, text=APP_NAME, font=("Arial", 16, "bold")).pack(side="left", anchor="w")
boton_configuracion = ctk.CTkButton(frame_titulo_y_config, text="", image=img_settings, width=30, height=30, command=abrir_ventana_configuracion_ui_cmd)
if img_settings is None: boton_configuracion.configure(text="⚙️")
boton_configuracion.pack(side="right")
frame_entrada_opciones = ctk.CTkFrame(sidebar_frame, fg_color="transparent"); frame_entrada_opciones.grid(row=1, column=0, padx=10, pady=5, sticky="new")
ctk.CTkLabel(frame_entrada_opciones, text="Ingresa URL de YouTube:").pack(pady=(0,2), anchor="w")
entrada_url_dm = ctk.CTkEntry(frame_entrada_opciones, placeholder_text="URL del video o playlist..."); entrada_url_dm.pack(pady=(0,5), fill="x")
frame_opciones_calidad = ctk.CTkFrame(frame_entrada_opciones, fg_color="transparent"); frame_opciones_calidad.pack(pady=(0,5), fill="x", anchor="w")
ctk.CTkLabel(frame_opciones_calidad, text="Calidad MP3:").pack(side="left", padx=(0,5)); combobox_calidad = ctk.CTkComboBox(frame_opciones_calidad, values=list(opciones_calidad_audio_map_app.keys()), variable=calidad_audio_display_var_app, width=170); combobox_calidad.pack(side="left")
frame_tipo_descarga_switch = ctk.CTkFrame(frame_entrada_opciones, fg_color="transparent"); frame_tipo_descarga_switch.pack(pady=(5,0), fill="x", anchor="w")
ctk.CTkLabel(frame_tipo_descarga_switch, text="Descargar Video (MP4):").pack(side="left", padx=(0,10))
switch_tipo_descarga = ctk.CTkSwitch(frame_tipo_descarga_switch, text="", variable=tipo_descarga_switch_var, onvalue="video", offvalue="audio"); switch_tipo_descarga.pack(side="left")

ui_elements_for_manager = {"entrada_url_widget": entrada_url_dm, "estado_general_actual_var": estado_general_actual_var, "video_titulo_actual_var": video_titulo_actual_var, "video_duracion_actual_var": video_duracion_actual_var, "etiqueta_imagen_actual": None, "barra_progreso_actual": barra_progreso_actual, "frame_elementos_cola": None, "calidad_audio_display_var": calidad_audio_display_var_app, "opciones_calidad_audio_map": opciones_calidad_audio_map_app, "frame_estado_y_acciones_actual": None, "estado_label_actual_widget": None, "tipo_descarga_var": tipo_descarga_switch_var}
download_mgr = DownloadManager(app, ui_elements_for_manager, CARPETA_MUSICA, opciones_calidad_audio_map_app, calidad_audio_display_var_app, status_icons_map, tipo_descarga_switch_var) 
boton_anadir_a_cola = ctk.CTkButton(frame_entrada_opciones, text="Añadir a Cola", image=img_add_queue, compound="left", command=lambda: download_mgr.gestionar_nueva_url(entrada_url_dm.get().strip()), height=40); boton_anadir_a_cola.pack(pady=(10,10), fill="x")

frame_gestion_cola = ctk.CTkFrame(sidebar_frame, fg_color="transparent"); frame_gestion_cola.grid(row=2, column=0, padx=10, pady=(10,0), sticky="ew"); frame_gestion_cola.grid_columnconfigure(0, weight=1); frame_gestion_cola.grid_columnconfigure(1, weight=0)
ctk.CTkLabel(frame_gestion_cola, text="Cola de Descargas:", font=("Arial", 13, "bold")).grid(row=0, column=0, sticky="sw", pady=(0,2))
boton_limpiar_cola = ctk.CTkButton(frame_gestion_cola, text="Limpiar Pendientes", height=28, font=("Arial", 10), width=100, command=download_mgr.limpiar_cola_pendientes_async); boton_limpiar_cola.grid(row=0, column=1, sticky="se", padx=(5,0), pady=(0,2))

queue_scrollable_area_dm = ctk.CTkScrollableFrame(sidebar_frame, label_text="", fg_color=("gray90", "gray20"), corner_radius=6, border_width=1, border_color=("gray75", "gray30")); queue_scrollable_area_dm.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0,10)) 
ui_elements_for_manager["frame_elementos_cola"] = queue_scrollable_area_dm

main_content_frame = ctk.CTkFrame(app, fg_color="transparent", corner_radius=0); main_content_frame.grid(row=0, column=1, sticky="nsew", padx=(5,10), pady=10); main_content_frame.grid_rowconfigure(0, weight=1); main_content_frame.grid_columnconfigure(0, weight=1)
panel_descarga_actual = ctk.CTkFrame(main_content_frame, fg_color=("gray88", "gray22"), corner_radius=10, border_width=1, border_color=("gray75", "gray30")); panel_descarga_actual.grid(row=0, column=0, sticky="nsew", padx=0, pady=0); panel_descarga_actual.grid_columnconfigure(0, weight=1); panel_descarga_actual.grid_rowconfigure(1, weight=1) 
frame_info_video = ctk.CTkFrame(panel_descarga_actual, fg_color="transparent"); frame_info_video.grid(row=0, column=0, pady=(10,5), padx=10, sticky="new")
ctk.CTkLabel(frame_info_video, textvariable=video_titulo_actual_var, wraplength=400, justify="left", font=("Arial", 16, "bold")).pack(pady=(5,2), anchor="w")
ctk.CTkLabel(frame_info_video, textvariable=video_duracion_actual_var, justify="left", font=("Arial", 12)).pack(pady=(0,10), anchor="w")
etiqueta_imagen_actual = ctk.CTkLabel(panel_descarga_actual, text="Miniatura del video actual", fg_color="gray25", corner_radius=6); etiqueta_imagen_actual.grid(row=1, column=0, pady=5, padx=10, sticky="nsew"); setattr(etiqueta_imagen_actual, 'image_ref', None)
ui_elements_for_manager["etiqueta_imagen_actual"] = etiqueta_imagen_actual
frame_estado_y_acciones_actual_dm = ctk.CTkFrame(panel_descarga_actual, fg_color="transparent"); frame_estado_y_acciones_actual_dm.grid(row=2, column=0, pady=(10,10), padx=10, sticky="ew")
ui_elements_for_manager["frame_estado_y_acciones_actual"] = frame_estado_y_acciones_actual_dm
estado_label_actual_dm = ctk.CTkLabel(frame_estado_y_acciones_actual_dm, textvariable=estado_general_actual_var, font=("Arial", 11), wraplength=430); estado_label_actual_dm.pack(pady=(5,5)) 
ui_elements_for_manager["estado_label_actual_widget"] = estado_label_actual_dm
ui_elements_for_manager["barra_progreso_actual"] = barra_progreso_actual

frame_pie_pagina = ctk.CTkFrame(app, fg_color="transparent", height=50); frame_pie_pagina.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(5,10)); frame_pie_pagina.grid_columnconfigure(0, weight=1); frame_pie_pagina.grid_columnconfigure(1, weight=0) 
info_carpeta_descargas_label = ctk.CTkLabel(frame_pie_pagina, text=f"Carpeta por defecto: {CARPETA_MUSICA}", font=("Arial", 10), text_color="gray50", wraplength=400)
info_carpeta_descargas_label.grid(row=0, column=0, sticky="w", padx=(5,10), pady=5)
boton_abrir_carpeta = ctk.CTkButton(frame_pie_pagina, text="Abrir Carpeta", image=img_open_folder, compound="left", command=abrir_carpeta_descargas_ui_cmd, height=40, width=180) 
boton_abrir_carpeta.grid(row=0, column=1, sticky="e", padx=(10,5), pady=5)

app.cargar_imagen_para_gui = cargar_imagen_para_gui 
if boton_configuracion : ToolTip(boton_configuracion, lambda: "Configuración")
if boton_anadir_a_cola: ToolTip(boton_anadir_a_cola, lambda: "Añadir URL a la cola de descargas")
if boton_abrir_carpeta: ToolTip(boton_abrir_carpeta, lambda: f"Abrir carpeta por defecto:\n{CARPETA_MUSICA}")

def iniciar_verificacion_actualizaciones():
    if download_mgr and hasattr(download_mgr, 'ui') and download_mgr.ui.get("estado_general_actual_var") :
        threading.Thread(target=verificar_actualizaciones_en_hilo, 
                         args=(app, download_mgr.ui, False), # es_manual=False para inicio automático
                         daemon=True).start()
    else: print("Advertencia: DownloadManager o UI refs no listos, no se verifican actualizaciones.")
app.after(2500, iniciar_verificacion_actualizaciones)

app.mainloop()