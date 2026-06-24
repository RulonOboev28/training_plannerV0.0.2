"""Персональная библиотека переиспользуемых компонентов (шаблонов).

Каждый шаблон хранит уровень, тип и полный payload элемента (включая позицию и
связи дочерних элементов). При вставке в план создаётся независимая копия с
новыми идентификаторами.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from core.database import DATA_DIR, ensure_dirs
from core.models import (
    HierarchyLevel, TYPE_BY_KEY, TYPE_KEYS, Exercise,
    element_type_key, level_of, regenerate_ids,
)

LIBRARY_FILE = DATA_DIR / "library.json"


def load_entries() -> List[Dict]:
    if not LIBRARY_FILE.exists():
        return []
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_entries(entries: List[Dict]) -> None:
    ensure_dirs()
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def entries_for_level(level: HierarchyLevel) -> List[Dict]:
    return [e for e in load_entries() if e.get("level") == level.value]


def add_element(element) -> Dict:
    """Сохраняет элемент как шаблон."""
    entry = {
        "title": getattr(element, "title", "Шаблон"),
        "type": element_type_key(element),
        "level": level_of(element).value,
        "payload": element.to_dict(),
    }
    entries = load_entries()
    entries.append(entry)
    save_entries(entries)
    return entry


def remove_entry(index: int) -> None:
    entries = load_entries()
    if 0 <= index < len(entries):
        del entries[index]
        save_entries(entries)


def build_element(entry: Dict):
    """Восстанавливает НЕЗАВИСИМУЮ копию элемента из шаблона."""
    cls = TYPE_BY_KEY.get(entry.get("type", "exercise"), Exercise)
    payload = dict(entry.get("payload", {}))
    element = cls.from_dict(payload)
    regenerate_ids(element)
    return element


def export_library(filepath: str) -> str:
    path = Path(filepath)
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(load_entries(), f, ensure_ascii=False, indent=2)
    return str(path)


def import_library(filepath: str, merge: bool = True) -> int:
    """Импортирует шаблоны из файла. Возвращает число добавленных."""
    with open(filepath, "r", encoding="utf-8") as f:
        incoming = json.load(f)
    if not isinstance(incoming, list):
        return 0
    entries = load_entries() if merge else []
    entries.extend(incoming)
    save_entries(entries)
    return len(incoming)
