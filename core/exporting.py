"""Экспорт плана в табличный вид (CSV).

Чистая логика без Qt: разворачивает иерархию плана в плоскую таблицу, где
уровень элемента обозначен отступом-колонкой. Рендер полотна в PNG/PDF живёт
в виджете полотна (нужен QPainter), а здесь — только данные.
"""
from __future__ import annotations

import csv
import io
from typing import List

from core.models import (
    AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, TrainingPlan,
    Workout, get_children, level_of,
)

HEADER = ["Уровень", "Название", "Тип", "Длительность", "Объём, км", "Заметки"]


def _type_text(element) -> str:
    if isinstance(element, Exercise):
        return element.exercise_type.value
    if isinstance(element, Workout):
        return element.workout_type.value
    if isinstance(element, (Microcycle, Mesocycle)):
        return element.cycle_type.value
    return ""


def _duration_text(element) -> str:
    if isinstance(element, Exercise):
        return f"{element.duration_minutes} мин" if element.duration_minutes else ""
    if isinstance(element, Workout):
        return f"{element.duration_minutes} мин" if element.duration_minutes else ""
    if isinstance(element, Microcycle):
        return f"{element.duration_days} дн."
    if isinstance(element, Mesocycle):
        return f"{element.duration_weeks} нед."
    if isinstance(element, Macrocycle):
        return f"{element.duration_months} мес."
    if isinstance(element, AnnualPlan):
        return str(element.year)
    return ""


def _volume_text(element) -> str:
    if isinstance(element, Exercise) and element.volume_km:
        v = element.volume_km
        return str(int(v)) if float(v).is_integer() else f"{v:.1f}"
    return ""


def plan_to_rows(plan: TrainingPlan) -> List[List[str]]:
    """Плоская таблица: первая строка — заголовок, далее элементы по порядку."""
    rows: List[List[str]] = [list(HEADER)]

    def walk(element) -> None:
        level_name = level_of(element).name
        indent = "    " * (6 - level_of(element).value)
        rows.append([
            level_name,
            indent + (element.title or ""),
            _type_text(element),
            _duration_text(element),
            _volume_text(element),
            (element.notes or "").replace("\n", " "),
        ])
        for child in get_children(element):
            walk(child)

    walk(plan.annual)
    return rows


def plan_to_csv(plan: TrainingPlan) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    for row in plan_to_rows(plan):
        writer.writerow(row)
    return buffer.getvalue()


def write_csv(filepath: str, plan: TrainingPlan) -> str:
    text = plan_to_csv(plan)
    # utf-8-sig — чтобы кириллица корректно открывалась в Excel
    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
        f.write(text)
    return filepath
