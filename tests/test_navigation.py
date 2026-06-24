"""Тесты навигации по уровням, памяти камеры и undo/redo на полотне."""
import pytest

from core.models import (
    AnnualPlan, Exercise, HierarchyLevel, Macrocycle, Mesocycle, Microcycle,
    TrainingPlan, Workout, get_children,
)


def _make_plan():
    w1 = Workout(title="W1")
    w2 = Workout(title="W2")
    micro = Microcycle(title="M1", workouts=[w1, w2])
    meso = Mesocycle(title="Meso", microcycles=[micro])
    macro = Macrocycle(title="Macro", mesocycles=[meso])
    annual = AnnualPlan(title="Год", macrocycles=[macro])
    return TrainingPlan(annual=annual), micro, meso, w1


@pytest.fixture()
def canvas(qapp):
    from ui.canvas.viewport import CanvasView
    view = CanvasView()
    view.animations_enabled = False
    return view


def test_initial_stage_is_workout_with_exercise_tiles(canvas):
    plan, micro, _meso, _w1 = _make_plan()
    canvas.load_plan(plan)
    assert canvas.scope_id == micro.id
    assert canvas.tile_level() == HierarchyLevel.EXERCISE
    assert canvas.area_level() == HierarchyLevel.WORKOUT


def test_go_up_remembers_origin_area(canvas):
    plan, micro, meso, _w1 = _make_plan()
    canvas.load_plan(plan)
    assert canvas.go_up() is True
    assert canvas.scope_id == meso.id
    # область, из которой вышли, запомнена и подсвечена
    assert canvas.active_area_id == micro.id
    assert canvas._scope_focus.get(meso.id) == micro.id


def test_enter_then_up_is_symmetric(canvas):
    plan, micro, meso, _w1 = _make_plan()
    canvas.load_plan(plan)
    canvas.go_up()                      # на уровень мезоцикла
    assert canvas.enter_scope(micro.id) is True
    assert canvas.scope_id == micro.id  # вернулись обратно


def test_undo_redo_create_tile(canvas):
    plan, _micro, _meso, w1 = _make_plan()
    canvas.load_plan(plan)
    before = len(get_children(canvas.plan.get(w1.id)))

    canvas.create_tile(Exercise(title="Новое"), area_id=w1.id)
    assert len(get_children(canvas.plan.get(w1.id))) == before + 1
    assert canvas.can_undo() is True

    canvas.undo()
    assert len(get_children(canvas.plan.get(w1.id))) == before

    canvas.redo()
    assert len(get_children(canvas.plan.get(w1.id))) == before + 1


def test_overlap_resolved_on_release(canvas):
    plan, _micro, _meso, w1 = _make_plan()
    canvas.load_plan(plan)
    # два упражнения в одной тренировке
    canvas.create_tile(Exercise(title="A"), area_id=w1.id)
    canvas.create_tile(Exercise(title="B"), area_id=w1.id)
    children = get_children(canvas.plan.get(w1.id))
    assert len(children) == 2
    # ставим второе ровно на первое и просим разрешить наложение
    children[1].pos_x = children[0].pos_x
    children[1].pos_y = children[0].pos_y
    node = canvas._nodes.get(children[1].id)
    assert node is not None
    canvas._resolve_overlap(node)
    a = (children[0].pos_x, children[0].pos_y)
    b = (children[1].pos_x, children[1].pos_y)
    assert a != b
