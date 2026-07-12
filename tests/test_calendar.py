"""Тесты привязки плана к календарным датам."""
from datetime import date

from core.calendar_map import (
    build_day_index, iter_plan_days, parse_plan_start, resolve_calendar_layers,
    scope_span,
)
from core.models import (
    AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, TrainingPlan, Workout,
)


def _demo_plan():
    workouts = [Workout(title=f"День {i + 1}") for i in range(7)]
    micro1 = Microcycle(title="Неделя 1", duration_days=7, workouts=workouts)
    micro2 = Microcycle(title="Неделя 2", duration_days=7,
                        workouts=[Workout(title="W1")])
    meso = Mesocycle(title="Мезо", duration_weeks=4, microcycles=[micro1, micro2])
    macro = Macrocycle(title="Макро", mesocycles=[meso])
    annual = AnnualPlan(title="Год", year=2026, macrocycles=[macro])
    return TrainingPlan(annual=annual, plan_start_date="2026-06-01"), micro1, meso


def test_plan_days_sequential():
    plan, micro1, _meso = _demo_plan()
    start = date(2026, 6, 1)
    days = list(iter_plan_days(plan, start))
    assert days[0].on_date == date(2026, 6, 1)
    assert days[0].workout_id is not None
    assert days[0].microcycle_id == micro1.id
    assert days[6].on_date == date(2026, 6, 7)
    assert days[7].on_date == date(2026, 6, 8)


def test_mesocycle_span_covers_four_weeks():
    plan, _micro1, meso = _demo_plan()
    start = date(2026, 6, 1)
    span = scope_span(plan, start, meso.id)
    assert span is not None
    assert (span.end - span.start).days + 1 == 28


def test_day_index_lookup():
    plan, _micro1, _meso = _demo_plan()
    start = parse_plan_start(plan.plan_start_date, plan)
    idx = build_day_index(plan, start)
    assert date(2026, 6, 3) in idx
    assert idx[date(2026, 6, 3)].is_training is True


def test_plan_start_date_roundtrip():
    plan, _, _ = _demo_plan()
    restored = TrainingPlan.from_dict(plan.to_dict())
    assert restored.plan_start_date == "2026-06-01"


def test_layers_microcycle_scope(qapp):
    from ui.canvas.viewport import CanvasView

    plan, micro1, meso = _demo_plan()
    canvas = CanvasView()
    canvas.load_plan(plan)
    start = parse_plan_start(plan.plan_start_date, plan)
    layers = resolve_calendar_layers(plan, canvas, start)
    assert len(layers.current_dates) == 7
    assert len(layers.parent_dates) == 28
    assert layers.current_title == micro1.title
    assert layers.parent_title == meso.title


def test_layers_single_day_when_exercise_selected(qapp):
    from ui.canvas.viewport import CanvasView

    plan, micro1, _meso = _demo_plan()
    w1 = micro1.workouts[0]
    canvas = CanvasView()
    canvas.load_plan(plan)
    canvas.create_tile(Exercise(title="Присед"), area_id=w1.id)
    node = canvas._nodes.get(canvas._selected_node().element.id if canvas._selected_node() else "")
    # select the exercise tile
    for n in canvas._nodes.values():
        if isinstance(n.element, Exercise):
            canvas._scene.clearSelection()
            n.setSelected(True)
            break
    start = parse_plan_start(plan.plan_start_date, plan)
    layers = resolve_calendar_layers(plan, canvas, start)
    assert len(layers.current_dates) == 1
    assert len(layers.parent_dates) == 7

