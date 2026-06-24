"""Пути к ресурсам приложения (исходники и собранный exe)."""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Корень проекта или временная папка PyInstaller (_MEIPASS)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Папка рядом с exe (для one-dir сборки) — demo, readme и т.д."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return app_root()


def resource_path(*parts: str) -> Path:
    return app_root().joinpath(*parts)
