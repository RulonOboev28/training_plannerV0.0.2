"""Сохранение и загрузка плана: автосохранение, история версий, экспорт/импорт."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from core.models import TrainingPlan

DATA_DIR = Path.home() / ".training_constructor"
PLANS_DIR = DATA_DIR / "plans"
HISTORY_DIR = DATA_DIR / "history"
AUTOSAVE_FILE = DATA_DIR / "autosave.tplan"

# История версий: не чаще раза в N секунд и не более чем LIMIT снимков.
HISTORY_MIN_INTERVAL = 60.0
HISTORY_LIMIT = 50
_last_history_time = 0.0


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)


def save_plan(name: str, plan: TrainingPlan) -> str:
    ensure_dirs()
    path = PLANS_DIR / f"{name}.tplan"
    _write(path, plan)
    return str(path)


def load_plan(name: str) -> Optional[TrainingPlan]:
    path = PLANS_DIR / f"{name}.tplan"
    return _read(path)


def list_plans() -> List[str]:
    ensure_dirs()
    return sorted(p.stem for p in PLANS_DIR.glob("*.tplan"))


def export_plan(filepath: str, plan: TrainingPlan) -> str:
    path = Path(filepath)
    if path.suffix.lower() != ".tplan":
        path = path.with_suffix(".tplan")
    _write(path, plan)
    return str(path)


def import_plan(filepath: str) -> Optional[TrainingPlan]:
    return _read(Path(filepath))


def save_autosave(plan: TrainingPlan) -> None:
    ensure_dirs()
    try:
        _write(AUTOSAVE_FILE, plan)
    except OSError:
        pass
    _append_history(plan)


def load_autosave() -> Optional[TrainingPlan]:
    if not AUTOSAVE_FILE.exists():
        return None
    return _read(AUTOSAVE_FILE)


# — история версий —

def _append_history(plan: TrainingPlan) -> None:
    """Складывает снимок плана с ограничением по частоте и количеству."""
    global _last_history_time
    now = time.time()
    if now - _last_history_time < HISTORY_MIN_INTERVAL:
        return
    _last_history_time = now
    try:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _write(HISTORY_DIR / f"autosave_{stamp}.tplan", plan)
        _trim_history()
    except OSError:
        pass


def _trim_history() -> None:
    files = sorted(HISTORY_DIR.glob("autosave_*.tplan"))
    excess = len(files) - HISTORY_LIMIT
    for path in files[:max(0, excess)]:
        path.unlink(missing_ok=True)


def list_history() -> List[Tuple[str, str]]:
    """Возвращает [(имя_файла, человекочитаемое_время)], свежие сверху."""
    if not HISTORY_DIR.exists():
        return []
    out: List[Tuple[str, str]] = []
    for path in sorted(HISTORY_DIR.glob("autosave_*.tplan"), reverse=True):
        stem = path.stem.replace("autosave_", "")
        try:
            dt = datetime.strptime(stem, "%Y%m%d_%H%M%S")
            label = dt.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            label = stem
        out.append((path.name, label))
    return out


def load_history(name: str) -> Optional[TrainingPlan]:
    return _read(HISTORY_DIR / name)


# — низкоуровневое —

def _write(path: Path, plan: TrainingPlan) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2)


def _read(path: Path) -> Optional[TrainingPlan]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TrainingPlan.from_dict(data)
    except (json.JSONDecodeError, OSError, KeyError, ValueError):
        return None
