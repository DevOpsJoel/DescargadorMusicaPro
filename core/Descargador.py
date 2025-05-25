# DescargarMusica/core/Descargador.py
from yt_dlp import YoutubeDL
import sys 
import os  

def resource_path_core(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

def _formato_duracion(segundos):
    if not isinstance(segundos, (int, float)) or segundos < 0: return "Desconocida"
    segundos = int(segundos); horas = segundos // 3600; minutos = (segundos % 3600) // 60; seg = segundos % 60
    return f"{horas:02d}:{minutos:02d}:{seg:02d}" if horas > 0 else f"{minutos:02d}:{seg:02d}"

def obtener_info_video(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'nocheckcertificate': True, 'extract_flat': 'in_playlist', 'forcejson': True}
    info_dict_final = None
    try:
        with YoutubeDL(ydl_opts) as ydl: info_dict = ydl.extract_info(url, download=False)
        if 'entries' in info_dict and info_dict['entries']: 
            playlist_titulo = info_dict.get('title', 'Playlist Desconocida'); videos_info_list = []
            for entry in info_dict['entries']:
                if entry and entry.get('url'): videos_info_list.append({'titulo_estimado': entry.get('title', f"Video de {playlist_titulo}"), 'webpage_url': entry.get('url')})
            return {'tipo': 'playlist', 'titulo_playlist': playlist_titulo, 'videos': videos_info_list, 'cantidad_videos': len(videos_info_list)} if videos_info_list else {'tipo': 'error', 'mensaje': f"Playlist '{playlist_titulo}' vacía."}
        elif 'entries' not in info_dict and info_dict.get('id'): 
            if not info_dict.get('duration') or not info_dict.get('thumbnail'):
                ydl_opts_video_detallado = ydl_opts.copy(); ydl_opts_video_detallado.pop('extract_flat', None)
                with YoutubeDL(ydl_opts_video_detallado) as ydl_video: info_dict_final = ydl_video.extract_info(url, download=False)
            else: info_dict_final = info_dict
            if info_dict_final:
                return {'tipo': 'video', 'titulo': info_dict_final.get('title', '?'), 'duracion': _formato_duracion(info_dict_final.get('duration', 0)),
                        'thumbnail': info_dict_final.get('thumbnail', ''), 'webpage_url': info_dict_final.get('webpage_url', url)}
            else: return {'tipo': 'error', 'mensaje': "No se pudo obtener info detallada del video."}
        else: return {'tipo': 'error', 'mensaje': "URL no reconocida."}
    except Exception as e: print(f"Excepción en obtener_info_video para {url}: {e}"); return {'tipo': 'error', 'mensaje': f"Error al procesar URL: {str(e)}"}

def procesar_y_descargar_item(url, ruta_salida, progreso_hook=None, calidad_audio_kbps="192", tipo_descarga="audio"):
    ffmpeg_exe_path = resource_path_core(os.path.join('ffmpeg', 'bin', 'ffmpeg.exe'))
    ffmpeg_location_to_use = ffmpeg_exe_path if os.path.exists(ffmpeg_exe_path) else None
    if ffmpeg_location_to_use: print(f"Usando ffmpeg desde: {ffmpeg_location_to_use}")
    else: print(f"ADVERTENCIA: ffmpeg.exe no encontrado en {ffmpeg_exe_path}. Usando PATH.")

    opciones = {
        'outtmpl': f'{ruta_salida}/%(title)s.%(ext)s',
        'quiet': True, 'no_warnings': True, 'progress_hooks': [progreso_hook] if progreso_hook else [],
        'noplaylist': True, 'ffmpeg_location': ffmpeg_location_to_use, 'nocheckcertificate': True
    }

    if tipo_descarga == "audio":
        opciones['format'] = 'bestaudio/best'
        opciones['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': str(calidad_audio_kbps),
        }]
        print(f"Descargando AUDIO MP3 ({calidad_audio_kbps}kbps) para: {url}")
    elif tipo_descarga == "video":
        # --- LÓGICA CORREGIDA PARA VIDEO ---
        # 1. Selector de formato más flexible: el mejor video + el mejor audio disponibles.
        opciones['format'] = 'bestvideo+bestaudio/best'
        # 2. Usar un postprocesador para asegurar que el contenedor final sea MP4.
        opciones['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]
        print(f"Descargando VIDEO (convirtiendo a MP4 si es necesario) para: {url}")
        # ------------------------------------
    else: # Fallback
        print(f"Tipo de descarga desconocido: {tipo_descarga}. Descargando audio por defecto.")
        opciones['format'] = 'bestaudio/best'
        opciones['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

    try:
        with YoutubeDL(opciones) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"Error durante la descarga ({tipo_descarga}) de {url}: {e}")
        raise