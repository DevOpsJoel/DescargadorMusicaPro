# DescargarMusica/gui/config_utils.py
import os
import sys
import json
import appdirs  # <--- appdirs SE IMPORTA AQUÍ
import customtkinter as ctk # Necesario para ctk.set_appearance_mode, etc.
from tkinter import messagebox # Para mostrar errores si la carpeta no se puede crear

# --- FUNCIÓN RESOURCE_PATH PARA LA GUI (PARA ASSETS EMPAQUETADOS) ---
def resource_path_gui(relative_path):
    """ Obtiene la ruta absoluta a un recurso, funciona para dev y para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

# --- CONSTANTES Y CONFIGURACIÓN ---
APP_NAME = "DescargarMusicaPro" # Nombre de la app
APP_AUTHOR = "Joel Márquez" 
APP_VERSION = "1.0.1" # Version de la app
URL_VERSION_JSON = ""

CONFIG_DIR = appdirs.user_config_dir(APP_NAME, APP_AUTHOR) 
try:
    os.makedirs(CONFIG_DIR, exist_ok=True)
except Exception as e:
    print(f"Error creando CONFIG_DIR {CONFIG_DIR}: {e}")
    # Fallback si no se puede crear el directorio de configuración del usuario
    script_gui_dir_fallback = os.path.dirname(os.path.abspath(__file__))
    directorio_proyecto_actual_fallback = os.path.dirname(script_gui_dir_fallback)
    CONFIG_DIR = os.path.join(directorio_proyecto_actual_fallback, ".config_local")
    os.makedirs(CONFIG_DIR, exist_ok=True)
    print(f"Usando CONFIG_DIR de fallback: {CONFIG_DIR}")

RUTA_CONFIG_JSON = os.path.join(CONFIG_DIR, "config.json")

home_dir = os.path.expanduser("~")
USER_MUSIC_DIR_FALLBACK = os.path.join(home_dir, "Music")
try:
    os.makedirs(USER_MUSIC_DIR_FALLBACK, exist_ok=True)
except OSError:
    USER_MUSIC_DIR_FALLBACK = home_dir 
    print(f"Advertencia: No se pudo crear/acceder a {os.path.join(home_dir, 'Music')}. Se usará {home_dir} como base para descargas por defecto.")

CARPETA_MUSICA_POR_DEFECTO_ABS = os.path.join(USER_MUSIC_DIR_FALLBACK, APP_NAME + "_Descargas")

CONFIG_DEFAULTS = {
    "download_folder": CARPETA_MUSICA_POR_DEFECTO_ABS,
    "appearance_mode": "Dark",
    "color_theme": "blue"
}

# Estas serán las variables 'globales' para la configuración, modificadas por las funciones de abajo
CARPETA_MUSICA = CARPETA_MUSICA_POR_DEFECTO_ABS 
config_app_actual = CONFIG_DEFAULTS.copy()


def cargar_configuracion_inicial():
    global CARPETA_MUSICA, config_app_actual
    try:
        with open(RUTA_CONFIG_JSON, 'r') as f:
            config_cargada = json.load(f)
        for key, default_value in CONFIG_DEFAULTS.items():
            config_app_actual[key] = config_cargada.get(key, default_value)
        print(f"Configuración cargada desde {RUTA_CONFIG_JSON}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Advertencia: Archivo '{RUTA_CONFIG_JSON}' no encontrado o corrupto ({e}). Usando y guardando valores por defecto.")
        config_app_actual = CONFIG_DEFAULTS.copy()
        # Intentar guardar los defaults inmediatamente para que el archivo exista la próxima vez
        try: 
            os.makedirs(os.path.dirname(RUTA_CONFIG_JSON), exist_ok=True)
            with open(RUTA_CONFIG_JSON, 'w') as f:
                json.dump(config_app_actual, f, indent=4)
            print(f"Archivo de configuración por defecto guardado en {RUTA_CONFIG_JSON}")
        except Exception as e_save:
            print(f"Error crítico: No se pudo guardar el archivo de configuración por defecto: {e_save}")

    CARPETA_MUSICA = os.path.abspath(config_app_actual["download_folder"]) 
    
    ctk.set_appearance_mode(config_app_actual["appearance_mode"])
    ctk.set_default_color_theme(config_app_actual["color_theme"])

    try:
        os.makedirs(CARPETA_MUSICA, exist_ok=True)
    except Exception as e_mkdir:
        print(f"Error creando carpeta de música '{CARPETA_MUSICA}': {e_mkdir}. Usando default absoluto del usuario.")
        CARPETA_MUSICA = CARPETA_MUSICA_POR_DEFECTO_ABS
        os.makedirs(CARPETA_MUSICA, exist_ok=True) # Intentar crear el default
        config_app_actual["download_folder"] = CARPETA_MUSICA 
        # No se puede usar messagebox aquí porque la GUI principal aún no se ha creado.

def guardar_configuracion_actual(info_label_widget=None):
    global CARPETA_MUSICA, config_app_actual
    
    config_app_actual["download_folder"] = CARPETA_MUSICA 
                                         
    try:
        os.makedirs(os.path.dirname(RUTA_CONFIG_JSON), exist_ok=True) 
        os.makedirs(CARPETA_MUSICA, exist_ok=True) 
        with open(RUTA_CONFIG_JSON, 'w') as f:
            json.dump(config_app_actual, f, indent=4)
        
        if info_label_widget: 
             info_label_widget.configure(text=f"Carpeta por defecto: {CARPETA_MUSICA}")
        print(f"Configuración guardada en {RUTA_CONFIG_JSON}")
        return True # Indicar éxito
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        # Devolver False para que la ventana de config sepa que no se pudo guardar
        return False