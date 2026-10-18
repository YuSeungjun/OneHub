# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# Custom PyInstaller builds must explicitly carry the EJS solver and its metadata.
datas = collect_data_files('yt_dlp_ejs') + copy_metadata('yt-dlp-ejs')
datas += collect_data_files('imageio_ffmpeg')

a = Analysis(
    [os.path.join('backend', 'main.py')],
    pathex=['backend'],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules('yt_dlp_ejs'),
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'numpy', 'pandas', 'matplotlib', 'scipy', 'IPython', 'jupyter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='onehub_backend', debug=False, strip=False, upx=False,
    console=True,
)
# Electron already distributes a directory. Keep Python/FFmpeg beside the
# executable instead of unpacking 120 MB into a fresh temp folder on every run.
coll = COLLECT(
    exe, a.binaries, a.datas,
    name='onehub_backend', strip=False, upx=False,
)
