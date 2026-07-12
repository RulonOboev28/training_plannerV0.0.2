"""Тесты дат элементов плана."""
from datetime import date

from core.calendar_map import (
    computed_scope_span, element_date_info, format_iso, parse_plan_start,
    scope_span,
)
from core.models import (
    AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, TrainingPlan, Workout,
)


def _demo_plan():
    workouts = [Workout(title=f"День {i + 1}") for i in range(7)]
    micro = Microcycle(title="Неделя 1", duration_days=7, workouts=workouts)
    meso = Mesocycle(title="Мезо", duration_weeks=4, microcycles=[micro])
    macro = Macrocycle(title="Макро", mesocycles=[meso])
    annual = AnnualPlan(title="Год", year=2026, macrocycles=[macro])
    return TrainingPlan(annual=annual, plan_start_date="2026-06-01"), micro, meso, workouts[0]


def test_computed_microcycle_span():
    plan, micro, _meso, _w = _demo_plan()
    start = parse_plan_start(plan.plan_start_date, plan)
    span = computed_scope_span(plan, start, micro.id)
    assert span is not None
    assert span.start == date(2026, 6, 1)
    assert span.end == date(2026, 6, 7)


def test_explicit_dates_override_computed():
    plan, micro, _meso, _w = _demo_plan()
    micro.start_date = "2026-07-01"
    micro.end_date = "2026-07-07"
    start = parse_plan_start(plan.plan_start_date, plan)
    span = scope_span(plan, start, micro.id)
    assert span.start == date(2026, 7, 1)
    assert span.end == date(2026, 7, 7)


def test_exercise_scheduled_date():
    plan, micro, _meso, w0 = _demo_plan()
    ex = Exercise(title="Бег", scheduled_date="2026-06-03")
    w0.exercises.append(ex)
    plan.reindex()
    start = parse_plan_start(plan.plan_start_date, plan)
    info = element_date_info(plan, ex.id)
    assert info.start == date(2026, 6, 3)
    assert info.start_overridden is True


def test_workout_computed_single_day():
    plan, _micro, _meso, w0 = _demo_plan()
    start = parse_plan_start(plan.plan_start_date, plan)
    info = element_date_info(plan, w0.id)
    assert info.start == date(2026, 6, 1)
    assert info.end == date(2026, 6, 1)


def test_date_fields_serialize():
    plan, micro, _meso, _w = _demo_plan()
    micro.start_date = format_iso(date(2026, 8, 1))
    restored = TrainingPlan.from_dict(plan.to_dict())
    m2 = restored.get(micro.id)
    assert m2.start_date == "2026-08-01"
