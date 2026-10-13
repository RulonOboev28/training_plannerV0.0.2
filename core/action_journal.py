"""Журнал последних действий с датой из календаря плана (не время сохранения)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import date
from typing import Deque, List, Optional, Tuple

from core.calendar_map import element_date_info, format_display
from core.models import (
    AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, TrainingPlan, Workout,
)


@dataclass(frozen=True)
class ActionEntry:
    text: str
    calendar_date: Optional[date]
    hist_index: int


def _calendar_date(plan: TrainingPlan, element_id: Optional[str]) -> Optional[date]:
    if not element_id:
        return None
    info = element_date_info(plan, element_id)
    return info.computed_start or info.start


def _label(el) -> str:
    if el is None:
        return "элемент"
    mapping = {
        Exercise: "упражнение",
        Workout: "тренировка",
        Microcycle: "микроцикл",
        Mesocycle: "мезоцикл",
        Macrocycle: "макроцикл",
        AnnualPlan: "годичный план",
    }
    for cls, name in mapping.items():
        if isinstance(el, cls):
            return name
    return "элемент"


class ActionJournal:
    def __init__(self, limit: int = 25) -> None:
        self._limit = limit
        self._entries: Deque[ActionEntry] = deque(maxlen=limit)
        self._last_key: Optional[Tuple] = None

    def clear(self) -> None:
        self._entries.clear()
        self._last_key = None

    def entries(self) -> List[ActionEntry]:
        return list(self._entries)

    def record(self, plan: TrainingPlan, coalesce_key, hist_index: int) -> None:
        if coalesce_key is None:
            return
        text, element_id = describe_action(plan, coalesce_key)
        if not text:
            return
        entry = ActionEntry(
            text=text,
            calendar_date=_calendar_date(plan, element_id),
            hist_index=hist_index,
        )
        if coalesce_key == self._last_key and self._entries:
            self._entries[-1] = entry
        else:
            self._entries.append(entry)
        self._last_key = coalesce_key

    def truncate_from(self, hist_index: int) -> None:
        """Удалить запись действия и все более новые."""
        kept = deque(maxlen=self._limit)
        for entry in self._entries:
            if entry.hist_index < hist_index:
                kept.append(entry)
        self._entries = kept
        self._last_key = None

    def shift_indices(self, delta: int) -> None:
        if delta == 0:
            return
        self._entries = deque(
            (ActionEntry(e.text, e.calendar_date, e.hist_index + delta)
             for e in self._entries if e.hist_index + delta >= 1),
            maxlen=self._limit,
        )


def describe_action(plan: TrainingPlan, coalesce_key) -> Tuple[str, Optional[str]]:
    if not coalesce_key or not isinstance(coalesce_key, tuple):
        return "", None
    kind = coalesce_key[0]
    element_id = coalesce_key[1] if len(coalesce_key) > 1 else None
    el = plan.get(element_id) if element_id else None
    title = getattr(el, "title", "") if el else ""
    quoted = f"«{title}»" if title else ""

    if kind == "edit" and el is not None:
        return f"Изменён {_label(el)} {quoted}".strip(), element_id
    if kind == "create" and el is not None:
        return f"Добавлен {_label(el)} {quoted}".strip(), element_id
    if kind == "delete":
        return f"Удалён элемент плана", element_id
    if kind == "date_bind" and el is not None:
        return f"Изменена дата {_label(el)} {quoted}".strip(), element_id
    if kind == "layout":
        return "Применена авто-расстановка", element_id
    return "", element_id


def format_entry(entry: ActionEntry) -> str:
    if entry.calendar_date is not None:
        return f"{entry.text} — {format_display(entry.calendar_date)}"
    return entry.text
