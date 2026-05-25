# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules

import docutranslate


datas = []
binaries = []

hiddenimports = [
    'markdown.extensions.tables',
    'pymdownx.arithmatex',
    'pymdownx.superfences',
    'pymdownx.highlight',
    'pygments',
    'docling_ibm_models',
    'docling_parse',
    'cv2',
    *collect_submodules('charset_normalizer'),
]

packages_to_collect = [
    'easyocr',
    'docling',
    'pygments',
    'docling_ibm_models',
]

for package in packages_to_collect:
    try:
        tmp_ret = collect_all(package)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception as e:
        print(f"Warning: Failed to collect resources for {package}: {e}")

for package_name in ('docling-ibm-models', 'docling-parse'):
    try:
        datas += copy_metadata(package_name)
    except Exception as e:
        print(f"Warning: Failed to copy metadata for {package_name}: {e}")

custom_datas = [
    ('./.venv/Lib/site-packages/docling_parse/pdf_resources', 'docling_parse/pdf_resources'),
    ('./docutranslate/static', 'docutranslate/static'),
    ('./docutranslate/template', 'docutranslate/template'),
]

for source, target in custom_datas:
    source_path = os.path.abspath(source)
    data = (source, target)
    if os.path.exists(source_path) and data not in datas:
        datas.append(data)
    elif not os.path.exists(source_path):
        print(f"Warning: Optional resource not found, skipped: {source_path}")

a = Analysis(
    ['docutranslate/app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='DocuTranslate_for_engineer-1.0.0-win',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='DocuTranslate.ico',
)
