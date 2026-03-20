# -*- mode: python ; coding: utf-8 -*-
import os
import sys

_IS_WINDOWS = sys.platform == 'win32'

_hidden_imports = ['multipart', 'python_multipart']
_datas = []
if _IS_WINDOWS:
    _hidden_imports += ['win32com', 'win32com.client', 'pythoncom', 'pywintypes']
else:
    _hidden_imports += ['hwp5', 'hwp5.xmlmodel', 'hwp5.binmodel', 'hwp5.recordstream', 'hwp5.dataio', 'hwp5.filestructure', 'hwp5.storage', 'hwp5.hwp5txt', 'docx', 'olefile', 'lxml', 'lxml.etree', 'six']
    # pyhwp XSL/리소스 파일 번들
    import hwp5 as _hwp5
    _hwp5_dir = os.path.dirname(_hwp5.__file__)
    _datas.append((os.path.join(_hwp5_dir, 'xsl'), os.path.join('hwp5', 'xsl')))
    # python-docx 템플릿 번들
    import docx as _docx
    _docx_dir = os.path.dirname(_docx.__file__)
    _datas.append((os.path.join(_docx_dir, 'templates'), os.path.join('docx', 'templates')))

a = Analysis(
    [os.path.join('backend', 'main.py')],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'unittest', 'pydoc', 'doctest',
        'pdb', 'lib2to3', 'test', 'setuptools',
        'numpy', 'pandas', 'matplotlib', 'scipy', 'PIL',
        'IPython', 'jupyter', 'notebook',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='onehub_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=_IS_WINDOWS,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
