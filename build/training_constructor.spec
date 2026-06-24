# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: сборка портативной папки с exe для Windows."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent

block_cipher = None

# PyQt6 — платформенные плагины и зависимости
pyqt_datas, pyqt_binaries, pyqt_hiddenimports = collect_all("PyQt6")

# Демо-план (генерируется скриптом build_release перед сборкой)
demo_datas = []
demo_dir = ROOT / "build" / "demo"
if demo_dir.is_dir():
    for path in demo_dir.glob("*.tplan"):
        demo_datas.append((str(path), "demo"))

datas = [
    (str(ROOT / "assets" / "styles"), "assets/styles"),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "docs" / "Руководство_пользователя.md"), "."),
] + demo_datas + pyqt_datas

binaries = pyqt_binaries

hiddenimports = pyqt_hiddenimports + [
    "core.database",
    "core.exporting",
    "core.library_store",
    "core.models",
    "core.paths",
    "core.geometry",
    "core.aggregates",
    "ui.main_window",
    "ui.canvas.viewport",
    "ui.canvas.nodes",
    "ui.canvas.connections",
    "ui.panels.library_panel",
    "ui.panels.properties_panel",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter", "matplotlib", "numpy", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TrainingPlanConstructor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TrainingPlanConstructor",
)
