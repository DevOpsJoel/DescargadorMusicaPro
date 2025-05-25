# DescargarMusica/core/Descargador.py
from yt_dlp import YoutubeDL
import sys 
import os  

def resource_path_core(relative_path):
    """ Obtiene la ruta absoluta a un recurso, funciona para desarrollo y para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

def _formato_duracion(segundos):
    if not isinstance(segundos, (int, float)) or segundos < 0:
        return "Desconocida"
    segundos = int(segundos) 
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    seg = segundos % 60
    if horas > 0:
        return f"{horas:02d}:{minutos:02d}:{seg:02d}"
    else:
        return f"{minutos:02d}:{seg:02d}"

def obtener_info_video(url):
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'skip_download': True,
        'nocheckcertificate': True, 'extract_flat': 'in_playlist', 
        'forcejson': True,
        
    }
    info_dict_final = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

        if 'entries' in info_dict and info_dict['entries']: 
            playlist_titulo = info_dict.get('title', 'Playlist Desconocida')
            videos_info_list = []
            for entry in info_dict['entries']:
                if entry and entry.get('url'):
                    videos_info_list.append({
                        'titulo_estimado': entry.get('title', f"Video de {playlist_titulo}"), 
                        'webpage_url': entry.get('url')})
            if videos_info_list:
                return {'tipo': 'playlist', 'titulo_playlist': playlist_titulo,
                        'videos': videos_info_list, 'cantidad_videos': len(videos_info_list)}
            else:
                return {'tipo': 'error', 'mensaje': f"Playlist '{playlist_titulo}' vacía."}
        
        elif 'entries' not in info_dict and info_dict.get('id'): 
            if not info_dict.get('duration') or not info_dict.get('thumbnail'):
                ydl_opts_video_detallado = ydl_opts.copy(); ydl_opts_video_detallado.pop('extract_flat', None)
                with YoutubeDL(ydl_opts_video_detallado) as ydl_video:
                    info_dict_final = ydl_video.extract_info(url, download=False)
            else: info_dict_final = info_dict
            if info_dict_final:
                return {'tipo': 'video', 'titulo': info_dict_final.get('title', '?'), 
                        'duracion': _formato_duracion(info_dict_final.get('duration', 0)),
                        'thumbnail': info_dict_final.get('thumbnail', ''), 
                        'webpage_url': info_dict_final.get('webpage_url', url)}
            else: return {'tipo': 'error', 'mensaje': "No se pudo obtener info detallada del video."}
        else: return {'tipo': 'error', 'mensaje': "URL no reconocida."}
    except Exception as e:
        print(f"Excepción en obtener_info_video para {url}: {e}")
        return {'tipo': 'error', 'mensaje': f"Error al procesar URL: {str(e)}"}

def descargar_audio(url, ruta_salida, progreso_hook=None, calidad_audio_kbps="192"):
    ffmpeg_exe_path = resource_path_core(os.path.join('ffmpeg', 'bin', 'ffmpeg.exe'))
    ffmpeg_location_to_use = ffmpeg_exe_path if os.path.exists(ffmpeg_exe_path) else None
    if ffmpeg_location_to_use: print(f"Usando ffmpeg desde: {ffmpeg_location_to_use}")
    else: print(f"ADVERTENCIA: ffmpeg.exe no en {ffmpeg_exe_path}. Usando PATH.")

    opciones = {
        'format': 'bestaudio/best', 'outtmpl': f'{ruta_salida}/%(title)s.%(ext)s',
        'quiet': True, 'no_warnings': True, 'progress_hooks': [progreso_hook] if progreso_hook else [],
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
                           'preferredquality': str(calidad_audio_kbps)}],
        'noplaylist': True, 'ffmpeg_location': ffmpeg_location_to_use, 'nocheckcertificate': True }
    try:
        with YoutubeDL(opciones) as ydl: ydl.download([url])
    except Exception as e:
        print(f"Error descargando {url} (calidad {calidad_audio_kbps}kbps): {e}"); raise