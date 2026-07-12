"""Привязка элементов плана к календарным датам.

Каждый день микроцикла соответствует одному календарному дню. Тренировки
занимают первые N дней; оставшиеся дни до duration_days — отдых. Мезоцикл
растягивается на duration_weeks × 7 дней (если микроциклы короче — добавляются
пустые дни в конце).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterator, List, Optional, Set, Tuple

from core.models import TrainingPlan, get_children


@dataclass(frozen=True)
class PlanDay:
    """Один календарный день внутри плана."""

    offset: int
    on_date: date
    workout_id: Optional[str]
    microcycle_id: str
    mesocycle_id: str
    macrocycle_id: str
    is_training: bool


@dataclass(frozen=True)
class ScopeSpan:
    """Диапазон дат для контейнера (микро-/мезоцикл)."""

    element_id: str
    title: str
    start: date
    end: date  # inclusive


def default_plan_start(plan: TrainingPlan) -> date:
    """Дата начала по умолчанию: 1 января года годового плана."""
    return date(plan.annual.year, 1, 1)


def parse_plan_start(value: Optional[str], plan: TrainingPlan) -> date:
    if plan.annual.start_date:
        parsed = parse_iso_date(plan.annual.start_date)
        if parsed is not None:
            return parsed
    if not value:
        return default_plan_start(plan)
    parsed = parse_iso_date(value)
    if parsed is not None:
        return parsed
    return default_plan_start(plan)


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        parts = value.split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        pass
    return None


def format_iso(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")


def format_display(d: Optional[date]) -> str:
    if d is None:
        return "—"
    return d.strftime("%d.%m.%Y")


@dataclass(frozen=True)
class ElementDateInfo:
    """Фактические и расчётные даты элемента."""

    start: Optional[date]
    end: Optional[date]
    computed_start: Optional[date]
    computed_end: Optional[date]
    start_overridden: bool
    end_overridden: bool


def plan_anchor(plan: TrainingPlan) -> date:
    return parse_plan_start(plan.plan_start_date, plan)


def computed_scope_span(plan: TrainingPlan, start: date,
                        element_id: str) -> Optional[ScopeSpan]:
    """Диапазон дат только по порядку элементов в плане (без ручных полей)."""
    element = plan.get(element_id)
    if element is None:
        return None
    from core.models import AnnualPlan, Exercise, Workout
    if isinstance(element, Exercise):
        if element.scheduled_date:
            d = parse_iso_date(element.scheduled_date)
            if d is not None:
                return ScopeSpan(element_id, element.title, d, d)
        workout_id = plan.parent_id(element_id)
        if workout_id:
            return computed_scope_span(plan, start, workout_id)
        return None
    if isinstance(element, AnnualPlan):
        all_days = list(_iter_computed_plan_days(plan, start))
        if not all_days:
            return None
        return ScopeSpan(
            element_id=element_id,
            title=element.title,
            start=all_days[0].on_date,
            end=all_days[-1].on_date,
        )
    if isinstance(element, Workout):
        for day in _iter_computed_plan_days(plan, start):
            if day.workout_id == element_id:
                return ScopeSpan(
                    element_id=element_id,
                    title=element.title,
                    start=day.on_date,
                    end=day.on_date,
                )
        return None
    days = list(_iter_computed_plan_days(plan, start))
    matching = [d for d in days if _day_belongs_to(d, element_id)]
    if not matching:
        return None
    return ScopeSpan(
        element_id=element_id,
        title=getattr(element, "title", ""),
        start=matching[0].on_date,
        end=matching[-1].on_date,
    )


def _explicit_span(element) -> Optional[ScopeSpan]:
    from core.models import Exercise, Workout
    if isinstance(element, Exercise):
        if not element.scheduled_date:
            return None
        d = parse_iso_date(element.scheduled_date)
        if d is None:
            return None
        return ScopeSpan(element.id, element.title, d, d)
    start = parse_iso_date(getattr(element, "start_date", None))
    if start is None:
        return None
    end = parse_iso_date(getattr(element, "end_date", None)) or start
    return ScopeSpan(element.id, getattr(element, "title", ""), start, end)


def element_date_info(plan: TrainingPlan, element_id: str) -> ElementDateInfo:
    start_anchor = plan_anchor(plan)
    computed = computed_scope_span(plan, start_anchor, element_id)
    element = plan.get(element_id)
    explicit = _explicit_span(element) if element is not None else None

    comp_start = computed.start if computed else None
    comp_end = computed.end if computed else None
    if explicit is not None:
        from core.models import Exercise
        return ElementDateInfo(
            start=explicit.start,
            end=explicit.end,
            computed_start=comp_start,
            computed_end=comp_end,
            start_overridden=True,
            end_overridden=bool(getattr(element, "end_date", None))
            or isinstance(element, Exercise),
        )
    return ElementDateInfo(
        start=comp_start,
        end=comp_end,
        computed_start=comp_start,
        computed_end=comp_end,
        start_overridden=False,
        end_overridden=False,
    )


def iter_plan_days(plan: TrainingPlan, start: date) -> Iterator[PlanDay]:
    """Проходит дни плана с учётом явных дат на контейнерах."""
    yield from _iter_computed_plan_days(plan, start)


def _iter_computed_plan_days(plan: TrainingPlan, start: date) -> Iterator[PlanDay]:
    """Проходит все дни плана в хронологическом порядке."""
    offset = 0
    for macro in plan.annual.macrocycles:
        for meso in macro.mesocycles:
            meso_start = offset
            for micro in meso.microcycles:
                workouts = list(micro.workouts)
                span = max(micro.duration_days, len(workouts))
                for day_idx in range(span):
                    workout = workouts[day_idx] if day_idx < len(workouts) else None
                    yield PlanDay(
                        offset=offset,
                        on_date=start + timedelta(days=offset),
                        workout_id=workout.id if workout else None,
                        microcycle_id=micro.id,
                        mesocycle_id=meso.id,
                        macrocycle_id=macro.id,
                        is_training=workout is not None,
                    )
                    offset += 1
            meso_span = meso.duration_weeks * 7
            meso_used = offset - meso_start
            while meso_used < meso_span:
                yield PlanDay(
                    offset=offset,
                    on_date=start + timedelta(days=offset),
                    workout_id=None,
                    microcycle_id="",
                    mesocycle_id=meso.id,
                    macrocycle_id=macro.id,
                    is_training=False,
                )
                offset += 1
                meso_used += 1


def build_day_index(plan: TrainingPlan, start: date) -> Dict[date, PlanDay]:
    return {d.on_date: d for d in iter_plan_days(plan, start)}


def day_by_offset(plan: TrainingPlan, start: date, offset: int) -> Optional[PlanDay]:
    for day in iter_plan_days(plan, start):
        if day.offset == offset:
            return day
        if day.offset > offset:
            break
    return None


def scope_span(plan: TrainingPlan, start: date, element_id: str) -> Optional[ScopeSpan]:
    """Диапазон дат для контейнера или одной тренировки."""
    element = plan.get(element_id)
    if element is None:
        return None
    explicit = _explicit_span(element)
    if explicit is not None:
        return explicit
    return computed_scope_span(plan, start, element_id)


def _day_belongs_to(day: PlanDay, element_id: str) -> bool:
    if not element_id:
        return False
    if day.workout_id == element_id:
        return True
    return element_id in (day.microcycle_id, day.mesocycle_id, day.macrocycle_id)


def parent_mesocycle_id(plan: TrainingPlan, scope_id: Optional[str]) -> Optional[str]:
    if scope_id is None:
        return None
    el = plan.get(scope_id)
    if el is None:
        return None
    from core.models import Mesocycle, Microcycle
    if isinstance(el, Microcycle):
        return plan.parent_id(scope_id)
    if isinstance(el, Mesocycle):
        return scope_id
    pid = plan.parent_id(scope_id)
    while pid:
        parent = plan.get(pid)
        if isinstance(parent, Mesocycle):
            return pid
        pid = plan.parent_id(pid)
    return None


def parent_microcycle_id(plan: TrainingPlan, scope_id: Optional[str]) -> Optional[str]:
    if scope_id is None:
        return None
    from core.models import Microcycle
    el = plan.get(scope_id)
    if isinstance(el, Microcycle):
        return scope_id
    pid = plan.parent_id(scope_id)
    while pid:
        parent = plan.get(pid)
        if isinstance(parent, Microcycle):
            return pid
        pid = plan.parent_id(pid)
    return None


def dates_for_area(plan: TrainingPlan, start: date, area_id: str) -> Set[date]:
    """Календарные даты, соответствующие области на полотне."""
    element = plan.get(area_id)
    if element is None:
        return set()
    from core.models import Microcycle, Workout
    if isinstance(element, Workout):
        for day in iter_plan_days(plan, start):
            if day.workout_id == area_id:
                return {day.on_date}
        return set()
    if isinstance(element, Microcycle):
        span = scope_span(plan, start, area_id)
        if span is None:
            return set()
        return _date_range(span.start, span.end)
    children = get_children(element)
    result: Set[date] = set()
    for child in children:
        result |= dates_for_area(plan, start, child.id)
    return result


def _date_range(start: date, end: date) -> Set[date]:
    result: Set[date] = set()
    current = start
    while current <= end:
        result.add(current)
        current += timedelta(days=1)
    return result


def month_grid(year: int, month: int) -> List[Optional[date]]:
    """42 ячейки (6×7) для отображения месяца; None — пустая ячейка."""
    first = date(year, month, 1)
    # Понедельник = 0
    lead = (first.weekday()) % 7
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    days_in_month = (next_month - first).days
    cells: List[Optional[date]] = [None] * lead
    for d in range(1, days_in_month + 1):
        cells.append(date(year, month, d))
    while len(cells) < 42:
        cells.append(None)
    return cells[:42]


MONTH_NAMES_RU = (
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

WEEKDAY_NAMES_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

# Прозрачность слоёв календаря
LAYER_CURRENT_ALPHA = 0.65
LAYER_PARENT_ALPHA = 0.30

# Цвета слоёв (текущий уровень / уровень выше)
COLOR_CURRENT = "#3d9970"
COLOR_PARENT = "#1e2786"


@dataclass(frozen=True)
class CalendarLayers:
    """Два подсвечиваемых диапазона: текущий уровень и родительский."""

    current_title: str
    parent_title: str
    current_dates: Set[date]
    parent_dates: Set[date]
    anchor_date: date


def _dates_from_span(span: Optional[ScopeSpan]) -> Set[date]:
    if span is None:
        return set()
    return _date_range(span.start, span.end)


def resolve_calendar_layers(plan: TrainingPlan, canvas, start: date) -> CalendarLayers:
    """Определяет подсветку по текущей стадии полотна.

    Внутри микроцикла: по умолчанию зелёный = весь микроцикл, синий = мезоцикл.
    Если выбрано упражнение — зелёный = один день (тренировка), синий = микроцикл.
    На уровне мезоцикла: зелёный = микроцикл, синий = мезоцикл.
    """
    from core.models import Exercise, HierarchyLevel, Mesocycle, Microcycle

    area_level = canvas.area_level()
    scope_id = canvas.scope_id
    active_id = canvas.active_area_id
    selected = canvas.get_selected_element()
    empty = CalendarLayers("", "", set(), set(), start)

    if scope_id is None:
        return empty

    scope_el = plan.get(scope_id)
    if scope_el is None:
        return empty

    def _first_area_id() -> Optional[str]:
        areas = canvas._areas_list()
        return areas[0].id if areas else None

    if isinstance(scope_el, Microcycle):
        meso_id = plan.parent_id(scope_id)
        micro_span = scope_span(plan, start, scope_id)
        meso_span = scope_span(plan, start, meso_id) if meso_id else None

        if isinstance(selected, Exercise):
            workout_id = active_id or _first_area_id()
            cur_span = scope_span(plan, start, workout_id) if workout_id else None
            anchor = cur_span.start if cur_span else (
                micro_span.start if micro_span else start)
            return CalendarLayers(
                current_title=cur_span.title if cur_span else "",
                parent_title=micro_span.title if micro_span else "",
                current_dates=_dates_from_span(cur_span),
                parent_dates=_dates_from_span(micro_span),
                anchor_date=anchor,
            )

        anchor = micro_span.start if micro_span else start
        return CalendarLayers(
            current_title=micro_span.title if micro_span else "",
            parent_title=meso_span.title if meso_span else "",
            current_dates=_dates_from_span(micro_span),
            parent_dates=_dates_from_span(meso_span),
            anchor_date=anchor,
        )

    if area_level == HierarchyLevel.MICROCYCLE and isinstance(scope_el, Mesocycle):
        micro_id = active_id or _first_area_id()
        cur_span = scope_span(plan, start, micro_id) if micro_id else None
        par_span = scope_span(plan, start, scope_id)
        anchor = cur_span.start if cur_span else start
        return CalendarLayers(
            current_title=cur_span.title if cur_span else "",
            parent_title=par_span.title if par_span else "",
            current_dates=_dates_from_span(cur_span),
            parent_dates=_dates_from_span(par_span),
            anchor_date=anchor,
        )

    if area_level == HierarchyLevel.MESOCYCLE:
        meso_id = active_id or _first_area_id()
        cur_span = scope_span(plan, start, meso_id) if meso_id else None
        par_span = scope_span(plan, start, scope_id)
        anchor = cur_span.start if cur_span else start
        return CalendarLayers(
            current_title=cur_span.title if cur_span else "",
            parent_title=par_span.title if par_span else "",
            current_dates=_dates_from_span(cur_span),
            parent_dates=_dates_from_span(par_span),
            anchor_date=anchor,
        )

    return empty


def add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    """Сдвиг месяца на delta (может быть отрицательным)."""
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, (idx % 12) + 1


def months_window(anchor: date, count: int = 4) -> List[Tuple[int, int]]:
    """count месяцев, начиная с (anchor.month - 1): контекст + текущий + вперёд."""
    first = add_months(anchor.year, anchor.month, -1)
    return [add_months(first[0], first[1], i) for i in range(count)]

