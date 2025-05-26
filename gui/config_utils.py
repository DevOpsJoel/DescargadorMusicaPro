# DescargarMusica/gui/config_utils.py
import os
import sys
import json
import appdirs
import customtkinter as ctk
from tkinter import messagebox # Para errores en creación de carpeta
# No necesitamos platform ni subprocess aquí si abrir_carpeta_descargas_cmd está en app.py

# Para la verificación de actualizaciones
import urllib.request
import urllib.parse 
import urllib.error
import tempfile 
import threading
import queue # Para la respuesta del messagebox en un hilo
import time
from packaging.version import parse as parse_version


# --- CONSTANTES DE LA APLICACIÓN Y VERSIÓN ---
APP_NAME = "DescargadorMusicaPro"
APP_AUTHOR = "Joel DevOps" 
APP_VERSION = "1.0.3"
URL_VERSION_JSON = "https://raw.githubusercontent.com/DevOpsJoel/DescargadorMusicaPro/refs/heads/main/version.json" # <-- ¡REEMPLAZA CON TU URL REAL!


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
    try: os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception as e_fb: print(f"Error creando CONFIG_DIR de fallback {CONFIG_DIR}: {e_fb}")
    print(f"Usando CONFIG_DIR de fallback: {CONFIG_DIR}")
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
        # No guardar aquí inmediatamente, se podría guardar después de la creación de carpeta exitosa
    
    CARPETA_MUSICA = os.path.abspath(config_app_actual["download_folder"]) 
    ctk.set_appearance_mode(config_app_actual["appearance_mode"]); ctk.set_default_color_theme(config_app_actual["color_theme"])
    
    try: os.makedirs(CARPETA_MUSICA, exist_ok=True)
    except Exception as e_mkdir:
        print(f"Error creando carpeta de música '{CARPETA_MUSICA}': {e_mkdir}. Usando default.")
        CARPETA_MUSICA = CARPETA_MUSICA_POR_DEFECTO_ABS
        try:
            os.makedirs(CARPETA_MUSICA, exist_ok=True)
            config_app_actual["download_folder"] = CARPETA_MUSICA 
            # Guardar solo si el default tuvo que ser forzado por error de la carpeta configurada
            # Y solo si el archivo de config no existía o estaba corrupto.
            # Esta lógica puede ser compleja, mejor dejar que el usuario lo corrija en Settings.
        except Exception as e_fallback_mkdir:
             print(f"CRÍTICO: No se pudo crear ni la carpeta configurada ni la de fallback: {e_fallback_mkdir}")

def guardar_configuracion_actual(info_label_widget=None): # info_label_widget es opcional
    global CARPETA_MUSICA, config_app_actual, RUTA_CONFIG_JSON # Asegurar RUTA_CONFIG_JSON es accesible
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
        # No mostrar messagebox desde aquí, la ventana de config lo hará
        return False

# --- FUNCIONES DE ACTUALIZACIÓN DE LA APLICACIÓN ---
def verificar_actualizaciones_en_hilo(app_ref, ui_elements_dict, es_manual=False):
    global APP_VERSION, URL_VERSION_JSON 
    
    estado_general_var = ui_elements_dict.get("estado_general_actual_var") # Para mensajes
    barra_prog_ref = ui_elements_dict.get("barra_progreso_actual") # Para descarga de actualizador
    frame_pack_barra_ref = ui_elements_dict.get("frame_estado_y_acciones_actual")
    before_widget_barra_ref = ui_elements_dict.get("estado_label_actual_widget")

    if es_manual:
        if estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Verificando actualizaciones..."))
    print("Verificando actualizaciones...")
    try:
        req = urllib.request.Request(URL_VERSION_JSON, headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
        with urllib.request.urlopen(req, timeout=15) as response: data = json.load(response)
        
        latest_version_str, download_url, release_notes = data.get("latest_version"), data.get("download_url"), data.get("release_notes", "N/A")

        if not latest_version_str or not download_url: 
            print("Archivo version.json malformado o incompleto en el servidor.")
            if es_manual:
                app_ref.after(0, lambda: messagebox.showwarning("Error de Actualización", "No se pudo obtener la información de la nueva versión desde el servidor.", parent=app_ref))
                if estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Error al verificar. Intente más tarde."))
            return
        
        print(f"Versión Actual: {APP_VERSION}, Versión Servidor: {latest_version_str}")

        if parse_version(latest_version_str) > parse_version(APP_VERSION):
            print(f"Nueva versión encontrada: {latest_version_str}")
            respuesta_q = queue.Queue()
            def preguntar_actualizacion_gui():
                respuesta = messagebox.askyesno(
                    "Actualización Disponible",
                    f"¡Hay una nueva versión ({latest_version_str}) disponible!\n\n"
                    f"Notas de la versión:\n{release_notes}\n\n"
                    f"¿Quieres descargarla e instalarla ahora?",
                    parent=app_ref )
                respuesta_q.put(respuesta)
            app_ref.after(0, preguntar_actualizacion_gui)
            try:
                if respuesta_q.get(timeout=300): 
                    if estado_general_var: app_ref.after(0, lambda: estado_general_var.set(f"Descargando actualización v{latest_version_str}..."))
                    threading.Thread(target=descargar_y_ejecutar_actualizacion, 
                                     args=(download_url, latest_version_str, app_ref, ui_elements_dict), 
                                     daemon=True).start()
                elif es_manual: 
                    if estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Actualización cancelada por el usuario."))
            except queue.Empty:
                print("Usuario no respondió a la pregunta de actualización o se agotó el tiempo.")
                if es_manual and estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Verificación de actualización: Sin respuesta."))
        else: 
            print("La aplicación ya está actualizada.")
            if es_manual: 
                app_ref.after(0, lambda: messagebox.showinfo("Actualizaciones", f"Tu aplicación ({APP_NAME} v{APP_VERSION}) ya está actualizada.", parent=app_ref))
                if estado_general_var: app_ref.after(0, lambda: estado_general_var.set(f"Versión {APP_VERSION} es la más reciente."))
    except urllib.error.URLError as e:
        print(f"Error de red al verificar actualizaciones: {e}")
        if es_manual:
            app_ref.after(0, lambda: messagebox.showwarning("Error de Red", f"No se pudo conectar al servidor para verificar actualizaciones.\nError: {e}", parent=app_ref))
            if estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Error de red al verificar."))
    except json.JSONDecodeError as e:
        print(f"Error decodificando version.json: {e}")
        if es_manual:
            app_ref.after(0, lambda: messagebox.showerror("Error de Actualización", f"El archivo de versión en el servidor está corrupto.\nError: {e}", parent=app_ref))
            if estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Error en datos de versión del servidor."))
    except Exception as e:
        print(f"Error inesperado al verificar actualizaciones: {e}")
        import traceback; traceback.print_exc()
        if es_manual:
            app_ref.after(0, lambda: messagebox.showerror("Error Desconocido", f"Ocurrió un error inesperado:\n{e}", parent=app_ref))
            if estado_general_var: app_ref.after(0, lambda: estado_general_var.set("Error inesperado al verificar."))

def descargar_y_ejecutar_actualizacion(url_instalador, nueva_version, app_ref, ui_elements_dict):
    global APP_NAME # Necesitamos APP_NAME para el nombre del archivo temporal
    barra_prog = ui_elements_dict.get("barra_progreso_actual")
    estado_var = ui_elements_dict.get("estado_general_actual_var")
    frame_pack_barra = ui_elements_dict.get("frame_estado_y_acciones_actual")
    before_widget_barra = ui_elements_dict.get("estado_label_actual_widget")
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"{APP_NAME}_Update_")
        nombre_base_instalador = os.path.basename(urllib.parse.urlparse(url_instalador).path)
        if not nombre_base_instalador or not nombre_base_instalador.lower().endswith((".exe", ".msi", ".dmg")): # Chequeo más genérico
            nombre_base_instalador = f"{APP_NAME}_Setup_v{nueva_version}.exe" # Default a .exe
        ruta_instalador_temp = os.path.join(temp_dir, nombre_base_instalador)
        print(f"Descargando instalador desde: {url_instalador} a {ruta_instalador_temp}")

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
            if respuesta_q_ejec.get(timeout=300): 
                print("Cerrando aplicación y ejecutando instalador..."); app_ref.after(0, app_ref.destroy); time.sleep(0.5) 
                if platform.system() == "Windows": os.startfile(ruta_instalador_temp)
                elif platform.system() == "Darwin": subprocess.run(['open', ruta_instalador_temp], check=True)
                else: subprocess.run(['xdg-open', ruta_instalador_temp], check=True) # Para Linux
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