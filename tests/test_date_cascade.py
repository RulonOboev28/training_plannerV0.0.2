"""Тесты каскадного обновления дат."""
from datetime import date

from core.date_cascade import apply_manual_date, bind_element_start_date, group_by_column
from core.models import (
    Exercise, HierarchyLevel, Macrocycle, Mesocycle, Microcycle, TrainingPlan, Workout,
)

def _micro_with_workouts(n: int = 4):
    workouts = [
        Workout(title=f"W{i + 1}", pos_x=i * 350.0, pos_y=0.0)
        for i in range(n)
    ]
    micro = Microcycle(title="M1", duration_days=7, workouts=workouts)
    meso = Mesocycle(title="Meso", microcycles=[micro])
    macro = Macrocycle(title="Macro", mesocycles=[meso])
    plan = TrainingPlan(annual=__import__("core.models", fromlist=["AnnualPlan"]).AnnualPlan(
        macrocycles=[macro]))
    return plan, micro, workouts


def test_group_by_column():
    w1 = Workout(pos_x=0, pos_y=0)
    w2 = Workout(pos_x=10, pos_y=100)
    w3 = Workout(pos_x=400, pos_y=0)
    cols = group_by_column([w1, w2, w3], lambda w: w.pos_x)
    assert len(cols) == 2
    assert len(cols[0]) == 2
    assert len(cols[1]) == 1


def test_workout_cascade_shifts_columns():
    plan, micro, workouts = _micro_with_workouts(4)
    apply_manual_date(plan, workouts[1].id, "start_date", date(2026, 6, 10))
    assert workouts[0].start_date == "2026-06-09"
    assert workouts[1].start_date == "2026-06-10"
    assert workouts[2].start_date == "2026-06-11"
    assert workouts[3].start_date == "2026-06-12"
    assert micro.start_date == "2026-06-09"
    assert micro.end_date == "2026-06-12"


def test_same_column_same_day():
    plan, micro, _ = _micro_with_workouts(1)
    w1 = Workout(title="AM", pos_x=100.0, pos_y=0.0)
    w2 = Workout(title="PM", pos_x=120.0, pos_y=150.0)
    micro.workouts = [w1, w2]
    plan.reindex()
    apply_manual_date(plan, w1.id, "start_date", date(2026, 6, 5))
    assert w1.start_date == "2026-06-05"
    assert w2.start_date == "2026-06-05"
    assert micro.start_date == "2026-06-05"
    assert micro.end_date == "2026-06-05"


def test_microcycle_start_redistributes_workouts():
    plan, micro, workouts = _micro_with_workouts(3)
    apply_manual_date(plan, micro.id, "start_date", date(2026, 7, 1))
    assert workouts[0].start_date == "2026-07-01"
    assert workouts[1].start_date == "2026-07-02"
    assert workouts[2].start_date == "2026-07-03"
    assert micro.end_date == "2026-07-03"


def test_bind_workout_start_date():
    plan, _, workouts = _micro_with_workouts(2)
    err = bind_element_start_date(plan, workouts[0], date(2026, 8, 15))
    assert err is None
    assert workouts[0].start_date == "2026-08-15"


def test_bind_exercise_requires_workout_stage():
    plan, _, workouts = _micro_with_workouts(1)
    ex = Exercise(title="Run", scheduled_date=None)
    workouts[0].exercises = [ex]
    plan.reindex()
    err = bind_element_start_date(
        plan, ex, date(2026, 8, 1), area_level=HierarchyLevel.EXERCISE)
    assert err is not None
    err = bind_element_start_date(
        plan, ex, date(2026, 8, 1), area_level=HierarchyLevel.WORKOUT)
    assert err is None
    assert ex.scheduled_date == "2026-08-01"
