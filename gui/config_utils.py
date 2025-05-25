# DescargarMusica/gui/config_utils.py
import os
import sys
import json
import appdirs
import customtkinter as ctk
from tkinter import messagebox, filedialog # filedialog para la ventana de config

# Para la verificación de actualizaciones
import urllib.request
import urllib.parse # Para urlparse
import urllib.error # Para manejo de errores de red
import tempfile 
import threading
import queue
import time
from packaging.version import parse as parse_version


# --- CONSTANTES DE LA APLICACIÓN Y VERSIÓN ---
APP_NAME = "DescargadorMusicaPro"
APP_AUTHOR = "Joel Márquez Magaña" 
APP_VERSION = "1.0.1"  
URL_VERSION_JSON = "https://raw.githubusercontent.com/TuUsuarioGitHub/TuRepositorio/main/version.json" 


# --- MANEJO DE RUTAS Y CONFIGURACIÓN ---
def resource_path_gui(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

CONFIG_DIR = appdirs.user_config_dir(APP_NAME, APP_AUTHOR) 
try: os.makedirs(CONFIG_DIR, exist_ok=True)
except Exception as e:
    print(f"Error creando CONFIG_DIR {CONFIG_DIR}: {e}")
    fallback_dir_base = os.path.dirname(os.path.abspath(__file__)) 
    fallback_dir_project = os.path.dirname(fallback_dir_base)    
    CONFIG_DIR = os.path.join(fallback_dir_project, ".config_local_DMPro")
    os.makedirs(CONFIG_DIR, exist_ok=True); print(f"Usando CONFIG_DIR de fallback: {CONFIG_DIR}")
RUTA_CONFIG_JSON = os.path.join(CONFIG_DIR, "config.json")

home_dir = os.path.expanduser("~"); USER_MUSIC_DIR_FALLBACK = os.path.join(home_dir, "Music")
try: os.makedirs(USER_MUSIC_DIR_FALLBACK, exist_ok=True)
except OSError: USER_MUSIC_DIR_FALLBACK = home_dir
CARPETA_MUSICA_POR_DEFECTO_ABS = os.path.join(USER_MUSIC_DIR_FALLBACK, APP_NAME + "_Descargas")

CONFIG_DEFAULTS = {"download_folder": CARPETA_MUSICA_POR_DEFECTO_ABS, "appearance_mode": "Dark", "color_theme": "blue"}
CARPETA_MUSICA = CARPETA_MUSICA_POR_DEFECTO_ABS 
config_app_actual = CONFIG_DEFAULTS.copy()

def cargar_configuracion_inicial():
    global CARPETA_MUSICA, config_app_actual
    try:
        with open(RUTA_CONFIG_JSON, 'r') as f: config_cargada = json.load(f)
        for key, default_value in CONFIG_DEFAULTS.items(): config_app_actual[key] = config_cargada.get(key, default_value)
        print(f"Configuración cargada desde {RUTA_CONFIG_JSON}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Advertencia: '{RUTA_CONFIG_JSON}' no encontrado o corrupto ({e}). Usando defaults.")
        config_app_actual = CONFIG_DEFAULTS.copy()
        # No guardar aquí, se guarda si el usuario usa la ventana de config o si falla una creación de carpeta
    
    CARPETA_MUSICA = os.path.abspath(config_app_actual["download_folder"]) 
    ctk.set_appearance_mode(config_app_actual["appearance_mode"]); ctk.set_default_color_theme(config_app_actual["color_theme"])
    
    try: os.makedirs(CARPETA_MUSICA, exist_ok=True)
    except Exception as e_mkdir:
        print(f"Error creando carpeta de música '{CARPETA_MUSICA}': {e_mkdir}. Usando default.")
        CARPETA_MUSICA = CARPETA_MUSICA_POR_DEFECTO_ABS
        try:
            os.makedirs(CARPETA_MUSICA, exist_ok=True)
            config_app_actual["download_folder"] = CARPETA_MUSICA # Actualizar config si se usó fallback
            guardar_configuracion_actual() # Guardar el fallback
        except Exception as e_fallback_mkdir:
             print(f"CRÍTICO: No se pudo crear ni la carpeta configurada ni la de fallback: {e_fallback_mkdir}")
             # Aquí podría ser útil un messagebox si la GUI ya estuviera disponible,
             # pero como esto es al inicio, un print es lo más seguro.

def guardar_configuracion_actual(info_label_widget=None):
    global CARPETA_MUSICA, config_app_actual
    config_app_actual["download_folder"] = CARPETA_MUSICA 
    try:
        os.makedirs(os.path.dirname(RUTA_CONFIG_JSON), exist_ok=True); os.makedirs(CARPETA_MUSICA, exist_ok=True)
        with open(RUTA_CONFIG_JSON, 'w') as f: json.dump(config_app_actual, f, indent=4)
        if info_label_widget and info_label_widget.winfo_exists(): 
             info_label_widget.configure(text=f"Carpeta por defecto: {CARPETA_MUSICA}")
        print(f"Configuración guardada en {RUTA_CONFIG_JSON}")
        return True
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        return False

# --- FUNCIONES DE ACTUALIZACIÓN DE LA APLICACIÓN ---
def verificar_actualizaciones_en_hilo(app_ref, ui_elements_dict):
    global APP_VERSION, URL_VERSION_JSON # Usar las globales de este módulo
    print("Verificando actualizaciones...")
    try:
        req = urllib.request.Request(URL_VERSION_JSON, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
        with urllib.request.urlopen(req, timeout=15) as response: data = json.load(response)
        
        latest_version_str = data.get("latest_version")
        download_url = data.get("download_url")
        release_notes = data.get("release_notes", "No hay notas de la versión disponibles.")

        if not latest_version_str or not download_url: 
            print("Archivo version.json malformado o incompleto en el servidor.")
            return
        
        print(f"Versión Actual en APP_VERSION: {APP_VERSION}, Versión Servidor: {latest_version_str}")

        if parse_version(latest_version_str) > parse_version(APP_VERSION):
            print(f"Nueva versión encontrada: {latest_version_str}")
            respuesta_q = queue.Queue()
            def preguntar_actualizacion_gui():
                respuesta = messagebox.askyesno(
                    "Actualización Disponible",
                    f"¡Hay una nueva versión ({latest_version_str}) disponible!\n\n"
                    f"Notas de la versión:\n{release_notes}\n\n"
                    f"¿Quieres descargarla e instalarla ahora?",
                    parent=app_ref 
                )
                respuesta_q.put(respuesta)
            app_ref.after(0, preguntar_actualizacion_gui)

            try:
                if respuesta_q.get(timeout=300): # Esperar hasta 5 minutos
                    if ui_elements_dict.get("estado_general_actual_var"):
                        app_ref.after(0, lambda: ui_elements_dict["estado_general_actual_var"].set(f"Descargando actualización v{latest_version_str}..."))
                    
                    # Iniciar hilo para descargar y ejecutar el instalador
                    threading.Thread(target=descargar_y_ejecutar_actualizacion, 
                                     args=(download_url, latest_version_str, app_ref, ui_elements_dict), 
                                     daemon=True).start()
            except queue.Empty:
                print("Usuario no respondió a la pregunta de actualización o se agotó el tiempo.")
        else:
            print("La aplicación ya está actualizada.")
    except urllib.error.URLError as e:
        print(f"Error de red al verificar actualizaciones: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decodificando version.json: {e}")
    except Exception as e:
        print(f"Error inesperado al verificar actualizaciones: {e}")
        import traceback
        traceback.print_exc()

def descargar_y_ejecutar_actualizacion(url_instalador, nueva_version, app_ref, ui_elements_dict):
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"{APP_NAME}_Update_")
        nombre_base_instalador = os.path.basename(urllib.parse.urlparse(url_instalador).path)
        if not nombre_base_instalador or not nombre_base_instalador.lower().endswith(".exe"): 
            nombre_base_instalador = f"{APP_NAME}_Setup_v{nueva_version}.exe"
        ruta_instalador_temp = os.path.join(temp_dir, nombre_base_instalador)

        print(f"Descargando instalador desde: {url_instalador} a {ruta_instalador_temp}")
        
        barra_prog = ui_elements_dict.get("barra_progreso_actual")
        estado_var = ui_elements_dict.get("estado_general_actual_var")
        frame_pack_barra = ui_elements_dict.get("frame_estado_y_acciones_actual")
        before_widget_barra = ui_elements_dict.get("estado_label_actual_widget")

        def hook_descarga_actualizador(block_num, block_size, total_size):
            descargado = block_num * block_size
            if total_size > 0:
                porcentaje = descargado / total_size
                if barra_prog and barra_prog.winfo_exists(): app_ref.after(0, lambda p=porcentaje: barra_prog.set(p))
                if estado_var: app_ref.after(0, lambda p=porcentaje: estado_var.set(f"Descargando actualización: {p*100:.0f}%"))
            else: 
                if estado_var: app_ref.after(0, lambda d_bytes=descargado: estado_var.set(f"Descargando actualización: {d_bytes/1024/1024:.1f} MB"))

        if barra_prog and frame_pack_barra and before_widget_barra:
            app_ref.after(0, lambda: barra_prog.set(0))
            app_ref.after(0, lambda: barra_prog.pack(in_=frame_pack_barra, pady=(0,5), padx=0, fill="x", before=before_widget_barra))
        
        urllib.request.urlretrieve(url_instalador, ruta_instalador_temp, reporthook=hook_descarga_actualizador)
        if barra_prog and barra_prog.winfo_exists(): app_ref.after(0, lambda: barra_prog.set(1))
        if estado_var: app_ref.after(0, lambda: estado_var.set("Descarga de actualización completada."))

        respuesta_q_ejec = queue.Queue()
        def preguntar_ejec_gui():
            respuesta_q_ejec.put(messagebox.askyesno("Instalar Actualización", "Descarga finalizada.\nLa app se cerrará para instalar.\n¿Continuar?", parent=app_ref))
        app_ref.after(0, preguntar_ejec_gui)

        try:
            if respuesta_q_ejec.get(timeout=300): # Esperar hasta 5 minutos
                print("Cerrando aplicación y ejecutando instalador...")
                app_ref.after(0, app_ref.destroy); time.sleep(0.5) 
                os.startfile(ruta_instalador_temp)
            else: 
                if estado_var: app_ref.after(0, lambda: estado_var.set(f"Instalación v{nueva_version} cancelada."))
        except queue.Empty: 
            if estado_var: app_ref.after(0, lambda: estado_var.set(f"No se respondió para instalar v{nueva_version}."))
    except Exception as e:
        print(f"Error al descargar o ejecutar la actualización: {e}")
        if estado_var: app_ref.after(0, lambda: estado_var.set(f"Error al actualizar: {str(e)[:50]}"))
        app_ref.after(0, lambda: messagebox.showerror("Error Actualización", f"No se pudo completar:\n{e}", parent=app_ref))
    finally:
        if barra_prog and barra_prog.winfo_ismapped(): app_ref.after(0, lambda: barra_prog.pack_forget())