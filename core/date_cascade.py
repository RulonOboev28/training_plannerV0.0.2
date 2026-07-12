"""Каскадное обновление дат при ручном изменении.

Правила раскладки на полотне:
  • одна колонка (одинаковый pos_x) — один календарный день;
  • колонка правее — на следующий день (+1 день для тренировок);
  • внутри микроцикла смена даты одной тренировки сдвигает соседние колонки;
  • даты микро-/мезо-/макроцикла подтягиваются из дочерних элементов.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, List, Optional, Sequence, TypeVar

from core.calendar_map import format_iso, parse_iso_date
from core.models import (
    AnnualPlan, Exercise, HierarchyLevel, Macrocycle, Mesocycle, Microcycle,
    TrainingPlan, Workout,
)

T = TypeVar("T")

# Плитки в одной «колонке дня» (соседи по горизонтали в пределах зазора).
COLUMN_EPS = 80.0

# Шаг между колонками микроциклов внутри мезоцикла (дней).
MICROCOLUMN_DAY_STEP = 7


def bind_element_start_date(plan: TrainingPlan, element, on_date: date,
                            *, area_level: Optional[HierarchyLevel] = None
                            ) -> Optional[str]:
    """Привязать начало выбранного элемента к дате. None — успех, иначе сообщение об ошибке."""
    if isinstance(element, Exercise):
        if area_level != HierarchyLevel.WORKOUT:
            return "Для упражнения: выберите стадию «Тренировки» и элемент на полотне"
        apply_manual_date(plan, element.id, "scheduled_date", on_date)
    elif isinstance(element, Workout):
        apply_manual_date(plan, element.id, "start_date", on_date)
    elif isinstance(element, (Microcycle, Mesocycle, Macrocycle, AnnualPlan)):
        apply_manual_date(plan, element.id, "start_date", on_date)
    else:
        return "Этот элемент нельзя привязать к дате"
    return None


def apply_manual_date(plan: TrainingPlan, element_id: str,
                      field: str, new_date: date) -> None:
    """Применить ручную дату и разнести зависимости по плану."""
    element = plan.get(element_id)
    if element is None:
        return

    if isinstance(element, Exercise) and field == "scheduled_date":
        _cascade_exercise_date(plan, element, new_date)
    elif isinstance(element, Workout) and field == "start_date":
        _cascade_workout_date(plan, element, new_date)
    elif isinstance(element, Microcycle):
        if field == "start_date":
            _cascade_microcycle_start(plan, element, new_date)
        elif field == "end_date":
            element.end_date = format_iso(new_date)
            _sync_microcycle_from_workouts(element)
            _propagate_ancestors(plan, element.id)
    elif isinstance(element, Mesocycle):
        if field == "start_date":
            _cascade_mesocycle_start(plan, element, new_date)
        elif field == "end_date":
            element.end_date = format_iso(new_date)
            _propagate_ancestors(plan, element.id)
    elif isinstance(element, Macrocycle):
        if field == "start_date":
            _cascade_macrocycle_start(plan, element, new_date)
        elif field == "end_date":
            element.end_date = format_iso(new_date)
            _propagate_ancestors(plan, element.id)
    elif isinstance(element, AnnualPlan) and field == "start_date":
        iso = format_iso(new_date)
        element.start_date = iso
        plan.plan_start_date = iso
        _cascade_annual_start(plan, element, new_date)


def group_by_column(items: Sequence[T], pos: Callable[[T], float]) -> List[List[T]]:
    """Группирует элементы в колонки по pos_x (слева направо)."""
    if not items:
        return []
    ordered = sorted(items, key=lambda it: (pos(it), getattr(it, "pos_y", 0.0)))
    columns: List[List[T]] = []
    for item in ordered:
        placed = False
        for col in columns:
            if abs(pos(item) - pos(col[0])) <= COLUMN_EPS:
                col.append(item)
                placed = True
                break
        if not placed:
            columns.append([item])
    columns.sort(key=lambda col: pos(col[0]))
    return columns


def _column_index(columns: List[List[T]], item_id: str,
                  id_of: Callable[[T], str]) -> Optional[int]:
    for i, col in enumerate(columns):
        if any(id_of(x) == item_id for x in col):
            return i
    return None


def _apply_day_to_workout(workout: Workout, day: date) -> None:
    iso = format_iso(day)
    workout.start_date = iso
    for ex in workout.exercises:
        ex.scheduled_date = iso


def _cascade_workout_date(plan: TrainingPlan, workout: Workout,
                          anchor: date) -> None:
    micro = plan.parent_of(workout.id)
    if not isinstance(micro, Microcycle):
        workout.start_date = format_iso(anchor)
        for ex in workout.exercises:
            ex.scheduled_date = format_iso(anchor)
        return

    columns = group_by_column(micro.workouts, lambda w: w.pos_x)
    idx = _column_index(columns, workout.id, lambda w: w.id)
    if idx is None:
        _apply_day_to_workout(workout, anchor)
    else:
        for i, col in enumerate(columns):
            day = anchor + timedelta(days=i - idx)
            for w in col:
                _apply_day_to_workout(w, day)

    _sync_microcycle_from_workouts(micro)
    _propagate_ancestors(plan, micro.id)


def _cascade_exercise_date(plan: TrainingPlan, exercise: Exercise,
                           anchor: date) -> None:
    workout = plan.parent_of(exercise.id)
    if not isinstance(workout, Workout):
        exercise.scheduled_date = format_iso(anchor)
        return
    _cascade_workout_date(plan, workout, anchor)


def _cascade_microcycle_start(plan: TrainingPlan, micro: Microcycle,
                              anchor: date) -> None:
    columns = group_by_column(micro.workouts, lambda w: w.pos_x)
    if not columns:
        micro.start_date = format_iso(anchor)
        micro.end_date = format_iso(anchor + timedelta(days=max(0, micro.duration_days - 1)))
        _propagate_ancestors(plan, micro.id)
        return

    for i, col in enumerate(columns):
        day = anchor + timedelta(days=i)
        for w in col:
            _apply_day_to_workout(w, day)

    _sync_microcycle_from_workouts(micro)
    _propagate_ancestors(plan, micro.id)


def _cascade_mesocycle_start(plan: TrainingPlan, meso: Mesocycle,
                             anchor: date) -> None:
    columns = group_by_column(meso.microcycles, lambda m: m.pos_x)
    if not columns:
        meso.start_date = format_iso(anchor)
        _propagate_ancestors(plan, meso.id)
        return

    for i, col in enumerate(columns):
        mstart = anchor + timedelta(days=i * MICROCOLUMN_DAY_STEP)
        for micro in col:
            _cascade_microcycle_start(plan, micro, mstart)

    _sync_mesocycle_from_children(meso)
    _propagate_ancestors(plan, meso.id)


def _cascade_macrocycle_start(plan: TrainingPlan, macro: Macrocycle,
                              anchor: date) -> None:
    columns = group_by_column(macro.mesocycles, lambda m: m.pos_x)
    if not columns:
        macro.start_date = format_iso(anchor)
        _propagate_ancestors(plan, macro.id)
        return

    offset = 0
    for col in columns:
        mstart = anchor + timedelta(days=offset)
        for meso in col:
            _cascade_mesocycle_start(plan, meso, mstart)
        span = max((meso.duration_weeks * 7 for meso in col), default=MICROCOLUMN_DAY_STEP)
        offset += span

    _sync_macrocycle_from_children(macro)
    _propagate_ancestors(plan, macro.id)


def _cascade_annual_start(plan: TrainingPlan, annual: AnnualPlan,
                          anchor: date) -> None:
    columns = group_by_column(annual.macrocycles, lambda m: m.pos_x)
    if not columns:
        return

    offset = 0
    for col in columns:
        mstart = anchor + timedelta(days=offset)
        for macro in col:
            _cascade_macrocycle_start(plan, macro, mstart)
        span = max((macro.duration_months * 30 for macro in col), default=30)
        offset += span


def _collect_iso_dates(items: Sequence, attr: str) -> List[date]:
    result: List[date] = []
    for item in items:
        parsed = parse_iso_date(getattr(item, attr, None))
        if parsed is not None:
            result.append(parsed)
    return result


def _sync_microcycle_from_workouts(micro: Microcycle) -> None:
    starts = _collect_iso_dates(micro.workouts, "start_date")
    if not starts:
        return
    micro.start_date = format_iso(min(starts))
    micro.end_date = format_iso(max(starts))
    span = (max(starts) - min(starts)).days + 1
    if span > micro.duration_days:
        micro.duration_days = span


def _sync_mesocycle_from_children(meso: Mesocycle) -> None:
    starts = _collect_iso_dates(meso.microcycles, "start_date")
    ends = _collect_iso_dates(meso.microcycles, "end_date")
    if starts:
        meso.start_date = format_iso(min(starts))
    if ends:
        meso.end_date = format_iso(max(ends))


def _sync_macrocycle_from_children(macro: Macrocycle) -> None:
    starts = _collect_iso_dates(macro.mesocycles, "start_date")
    ends = _collect_iso_dates(macro.mesocycles, "end_date")
    if starts:
        macro.start_date = format_iso(min(starts))
    if ends:
        macro.end_date = format_iso(max(ends))


def _propagate_ancestors(plan: TrainingPlan, element_id: str) -> None:
    pid = plan.parent_id(element_id)
    while pid:
        parent = plan.get(pid)
        if isinstance(parent, Mesocycle):
            _sync_mesocycle_from_children(parent)
        elif isinstance(parent, Macrocycle):
            _sync_macrocycle_from_children(parent)
        elif isinstance(parent, AnnualPlan):
            starts = _collect_iso_dates(parent.macrocycles, "start_date")
            if starts:
                parent.start_date = format_iso(min(starts))
        pid = plan.parent_id(pid)


def clear_manual_dates_in_subtree(element) -> None:
    """Сбрасывает ручные даты у элемента и потомков."""
    from core.models import get_children

    if isinstance(element, Exercise):
        element.scheduled_date = None
        return
    if hasattr(element, "start_date"):
        element.start_date = None
    if hasattr(element, "end_date"):
        element.end_date = None
    for child in get_children(element):
        clear_manual_dates_in_subtree(child)
