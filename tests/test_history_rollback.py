import pytest

from core.models import AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, TrainingPlan, Workout


@pytest.fixture()
def canvas(qapp):
    from ui.canvas.viewport import CanvasView
    view = CanvasView()
    view.animations_enabled = False
    return view


def _plan():
    ex = Exercise(title="A")
    w = Workout(title="W", exercises=[ex])
    micro = Microcycle(title="M", workouts=[w])
    meso = Mesocycle(title="Meso", microcycles=[micro])
    macro = Macrocycle(title="Macro", mesocycles=[meso])
    annual = AnnualPlan(title="Год", macrocycles=[macro])
    return TrainingPlan(annual=annual), ex


def test_rollback_before_removes_actions(canvas):
    plan, ex = _plan()
    canvas.load_plan(plan)
    canvas.animations_enabled = False
    ex.title = "B"
    canvas.commit_state(("edit", ex.id))
    canvas.auto_layout()
    ex.title = "C"
    canvas.commit_state(("edit", ex.id))
    layout_entry = next(
        e for e in canvas.action_journal.entries() if "расстановка" in e.text.lower())
    assert canvas.rollback_before(layout_entry.hist_index)
    assert canvas.plan.get(ex.id).title == "B"
    assert all("расстановка" not in e.text.lower()
               for e in canvas.action_journal.entries())
