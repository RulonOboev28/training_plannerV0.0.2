"""Тесты авто-расстановки: колонки сверху вниз и однонаправленные связи."""
import math

import pytest

from core.models import (
    AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle,
    TrainingPlan, Workout, get_children,
)
from ui.canvas import nodes
from ui.canvas.viewport import AUTO_COL_GAP, AUTO_COL_MAX, AUTO_COL_MIN, AUTO_ROW_GAP


def _make_plan(n_exercises: int = 9):
    exercises = [Exercise(title=f"Ex{i}") for i in range(n_exercises)]
    workout = Workout(title="W1", exercises=exercises)
    micro = Microcycle(title="M1", workouts=[workout])
    meso = Mesocycle(title="Meso", microcycles=[micro])
    macro = Macrocycle(title="Macro", mesocycles=[meso])
    annual = AnnualPlan(title="Год", macrocycles=[macro])
    return TrainingPlan(annual=annual), workout, exercises


@pytest.fixture()
def canvas(qapp):
    from ui.canvas.viewport import CanvasView
    view = CanvasView()
    view.animations_enabled = False
    return view


def test_column_arrange_places_vertically_then_next_column(canvas):
    plan, workout, exercises = _make_plan(9)
    canvas.load_plan(plan)
    ordered, per_col = canvas._column_arrange(exercises)
    per_col = max(AUTO_COL_MIN, min(AUTO_COL_MAX, math.ceil(math.sqrt(9))))
    step_x = nodes.TILE_W + AUTO_COL_GAP
    step_y = nodes.TILE_H + AUTO_ROW_GAP
    for i, ex in enumerate(ordered):
        col = i // per_col
        row = i % per_col
        assert ex.pos_x == col * step_x
        assert ex.pos_y == row * step_y
        if i > 0:
            prev = ordered[i - 1]
            same_col = (i - 1) // per_col == col
            if same_col:
                assert ex.pos_y > prev.pos_y
            else:
                assert ex.pos_x > prev.pos_x
                assert ex.pos_y < prev.pos_y


def test_auto_layout_rebuilds_single_direction_chain(canvas):
    from core.models import Connection

    plan, workout, exercises = _make_plan(4)
    for i, ex in enumerate(exercises):
        ex.pos_x = 0.0
        ex.pos_y = i * (nodes.TILE_H + 50)
    a, b = exercises[0], exercises[1]
    a.connections.append(Connection(target_id=b.id))
    b.connections.append(Connection(target_id=a.id))
    canvas.load_plan(plan)
    canvas.auto_layout()
    children = get_children(workout)
    incoming: dict = {c.id: 0 for c in children}
    for child in children:
        for conn in child.connections:
            incoming[conn.target_id] = incoming.get(conn.target_id, 0) + 1
    for child in children:
        assert incoming[child.id] <= 1
    total = sum(len(ch.connections) for ch in children)
    assert total == len(children) - 1
    heads = [c for c in children if incoming[c.id] == 0]
    assert len(heads) == 1
    chain = [heads[0]]
    while chain[-1].connections:
        nxt = canvas.plan.get(chain[-1].connections[0].target_id)
        chain.append(nxt)
    assert len(chain) == len(children)
    assert [c.title for c in chain] == [f"Ex{i}" for i in range(4)]


def test_auto_layout_expands_area_height(canvas):
    plan, workout, exercises = _make_plan(9)
    canvas.load_plan(plan)
    canvas.auto_layout()
    rect = canvas._area_rects[workout.id]
    per_col = max(AUTO_COL_MIN, min(AUTO_COL_MAX, math.ceil(math.sqrt(9))))
    min_h = per_col * (nodes.TILE_H + AUTO_ROW_GAP)
    assert rect.height() >= min_h - nodes.TILE_H


def test_first_exercise_starts_at_top(canvas):
    plan, workout, exercises = _make_plan(6)
    for i, ex in enumerate(exercises):
        ex.pos_x = 100.0 * i
        ex.pos_y = 50.0
    canvas.load_plan(plan)
    ordered, _per_col = canvas._column_arrange(exercises)
    assert ordered[0].pos_y == 0.0
    assert ordered[0].pos_x == 0.0


def test_auto_layout_wrap_connection_kind(canvas):
    plan, workout, exercises = _make_plan(4)
    for i, ex in enumerate(exercises):
        ex.pos_x = 0.0
        ex.pos_y = i * (nodes.TILE_H + 50)
    canvas.load_plan(plan)
    canvas.auto_layout()
    children = get_children(workout)
    kinds = {c.kind for ch in children for c in ch.connections}
    assert "auto_down" in kinds
    assert "auto_wrap" in kinds
