"""Персональная библиотека шаблонов, сгруппированных в коллекции."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.database import DATA_DIR, ensure_dirs
from core.models import (
    HierarchyLevel, TYPE_BY_KEY, Exercise,
    element_type_key, level_of, regenerate_ids,
)

LIBRARY_FILE = DATA_DIR / "library.json"
DEFAULT_COLLECTION_TITLE = "Общие"


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _entry_from_element(element) -> Dict:
    return {
        "id": _new_id(),
        "title": getattr(element, "title", "Шаблон"),
        "type": element_type_key(element),
        "level": level_of(element).value,
        "payload": element.to_dict(),
    }


def _empty_library() -> Dict:
    return {"version": 2, "collections": []}


def clear_library() -> None:
    """Полностью очистить пользовательскую библиотеку."""
    save_library(_empty_library())


def load_library() -> Dict:
    if not LIBRARY_FILE.exists():
        return _empty_library()
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_library()
    if isinstance(data, list):
        return {
            "version": 2,
            "collections": [{
                "id": _new_id(),
                "title": DEFAULT_COLLECTION_TITLE,
                "entries": [_migrate_entry(e) for e in data],
            }],
        }
    if not isinstance(data, dict) or "collections" not in data:
        return _empty_library()
    return data


def _migrate_entry(raw: Dict) -> Dict:
    entry = dict(raw)
    entry.setdefault("id", _new_id())
    return entry


def save_library(data: Dict) -> None:
    ensure_dirs()
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_collections() -> List[Dict]:
    return list(load_library().get("collections", []))


def create_collection(title: str) -> str:
    data = load_library()
    cid = _new_id()
    data["collections"].append({"id": cid, "title": title.strip() or "Коллекция", "entries": []})
    save_library(data)
    return cid


def delete_collection(collection_id: str) -> bool:
    data = load_library()
    before = len(data["collections"])
    data["collections"] = [c for c in data["collections"] if c["id"] != collection_id]
    if len(data["collections"]) == before:
        return False
    save_library(data)
    return True


def rename_collection(collection_id: str, title: str) -> bool:
    data = load_library()
    for col in data["collections"]:
        if col["id"] == collection_id:
            col["title"] = title.strip() or col["title"]
            save_library(data)
            return True
    return False


def add_element(element, collection_id: Optional[str] = None) -> Dict:
    data = load_library()
    col = _find_collection(data, collection_id)
    entry = _entry_from_element(element)
    col["entries"].append(entry)
    save_library(data)
    return entry


def remove_entry(collection_id: str, entry_id: str) -> bool:
    data = load_library()
    col = _find_collection(data, collection_id)
    before = len(col["entries"])
    col["entries"] = [e for e in col["entries"] if e.get("id") != entry_id]
    if len(col["entries"]) == before:
        return False
    save_library(data)
    return True


def move_entry(from_col_id: str, entry_id: str,
               to_col_id: str, to_index: int) -> bool:
    data = load_library()
    src = _find_collection(data, from_col_id)
    dst = _find_collection(data, to_col_id)
    entry = None
    kept: List[Dict] = []
    for e in src["entries"]:
        if e.get("id") == entry_id:
            entry = e
        else:
            kept.append(e)
    src["entries"] = kept
    if entry is None:
        return False
    to_index = max(0, min(to_index, len(dst["entries"])))
    dst["entries"].insert(to_index, entry)
    save_library(data)
    return True


def _find_collection(data: Dict, collection_id: Optional[str]) -> Dict:
    cols = data.get("collections", [])
    if collection_id:
        for col in cols:
            if col["id"] == collection_id:
                return col
    if cols:
        return cols[0]
    col = {"id": _new_id(), "title": DEFAULT_COLLECTION_TITLE, "entries": []}
    cols.append(col)
    data["collections"] = cols
    save_library(data)
    return col


def entries_for_level(level: HierarchyLevel) -> List[Dict]:
    out: List[Dict] = []
    for col in list_collections():
        for entry in col.get("entries", []):
            if entry.get("level") == level.value:
                out.append(entry)
    return out


def collections_for_level(level: HierarchyLevel) -> List[Tuple[Dict, List[Dict]]]:
    """[(collection_meta, entries_for_level), ...]"""
    result: List[Tuple[Dict, List[Dict]]] = []
    for col in list_collections():
        entries = [e for e in col.get("entries", []) if e.get("level") == level.value]
        if entries:
            result.append((col, entries))
    return result


def build_element(entry: Dict):
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
        json.dump(load_library(), f, ensure_ascii=False, indent=2)
    return str(path)


def import_library(filepath: str, merge: bool = True) -> int:
    with open(filepath, "r", encoding="utf-8") as f:
        incoming = json.load(f)
    if isinstance(incoming, list):
        incoming = {
            "version": 2,
            "collections": [{"id": _new_id(), "title": "Импорт", "entries": incoming}],
        }
    if not isinstance(incoming, dict):
        return 0
    added = 0
    data = load_library() if merge else _empty_library()
    for col in incoming.get("collections", []):
        target = {
            "id": _new_id(),
            "title": col.get("title", "Импорт"),
            "entries": [_migrate_entry(e) for e in col.get("entries", [])],
        }
        added += len(target["entries"])
        data["collections"].append(target)
    save_library(data)
    return added


def save_entries(entries: List[Dict]) -> None:
    data = _empty_library()
    data["collections"][0]["entries"] = [_migrate_entry(e) for e in entries]
    save_library(data)
