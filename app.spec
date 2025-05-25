# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Definimos las rutas a tus carpetas de assets y ffmpeg
# Estas rutas son relativas a la ubicación de este archivo .spec
# (que debe estar en C:\MisProyectos\DescargarMusica\)
datas_to_include = [
    ('assets', 'assets'),       # Copia la carpeta 'assets' a una carpeta 'assets' en el bundle
    ('ffmpeg', 'ffmpeg')        # Copia la carpeta 'ffmpeg' a una carpeta 'ffmpeg' en el bundle
]

# Lista de submódulos a recolectar para que CustomTkinter y Pillow funcionen bien
collected_submodules = [
    'customtkinter',
    'PIL'
]

a = Analysis(
    ['gui/app.py'],  # Script principal de tu GUI
    pathex=[r'C:\MisProyectos\DescargarMusica'], # <--- RUTA RAÍZ DE TU PROYECTO
    binaries=[],
    datas=datas_to_include, # <--- Usamos la variable definida arriba
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    collect_submodules=collected_submodules # <--- Usamos la variable definida arriba
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [], # No se necesitan binaries aquí para --onedir si se usan en COLLECT
    name='DescargadorMusicaPro', # <--- NOMBRE DE TU APP
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # Puedes ponerlo a False si UPX da problemas o para compilar más rápido
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # <--- MUY IMPORTANTE: False para que no salga la ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/app_icon.ico' # <--- RUTA A TU ICONO .ICO
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas, # a.datas aquí asegura que los datos se copien en el directorio final
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DescargadorMusicaPro' # <--- NOMBRE DE LA CARPETA DE SALIDA EN 'dist'
)