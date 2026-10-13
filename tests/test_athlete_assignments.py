"""Пункт 1 roadmap: спортсмены группы и назначение упражнений в .tplan."""
import json
from pathlib import Path

from core.models import (
    AnnualPlan,
    AthleteProfile,
    Exercise,
    Macrocycle,
    Mesocycle,
    Microcycle,
    TrainingPlan,
    Workout,
    exercises_for_athlete,
)


def _plan_with_exercises(*exercises: Exercise) -> TrainingPlan:
    workout = Workout(title="W1", exercises=list(exercises))
    micro = Microcycle(workouts=[workout])
    meso = Mesocycle(microcycles=[micro])
    macro = Macrocycle(mesocycles=[meso])
    return TrainingPlan(annual=AnnualPlan(macrocycles=[macro]))


def test_athletes_and_assignments_roundtrip():
    a1 = AthleteProfile(id="a1", display_name="Иван", login="ivan")
    a2 = AthleteProfile(id="a2", display_name="Мария", login="maria")
    shared = Exercise(title="Разминка", assigned_to_all=True)
    personal = Exercise(
        title="Жим",
        assigned_to_all=False,
        assigned_athlete_ids=["a1"],
    )
    plan = _plan_with_exercises(shared, personal)
    plan.athletes = [a1, a2]

    data = plan.to_dict()
    restored = TrainingPlan.from_dict(data)

    assert len(restored.athletes) == 2
    assert restored.athlete_by_login("ivan").display_name == "Иван"
    exs = list(restored.annual.macrocycles[0].mesocycles[0]
               .microcycles[0].workouts[0].exercises)
    assert exs[0].assigned_to_all is True
    assert exs[1].assigned_athlete_ids == ["a1"]


def test_filter_exercises_for_two_athletes():
    a1 = AthleteProfile(id="a1", display_name="A", login="a")
    a2 = AthleteProfile(id="a2", display_name="B", login="b")
    plan = _plan_with_exercises(
        Exercise(title="Для всех"),
        Exercise(title="Только A", assigned_to_all=False, assigned_athlete_ids=["a1"]),
        Exercise(title="Только B", assigned_to_all=False, assigned_athlete_ids=["a2"]),
    )
    plan.athletes = [a1, a2]

    titles_a = {ex.title for ex in exercises_for_athlete(plan, "a1")}
    titles_b = {ex.title for ex in exercises_for_athlete(plan, "a2")}

    assert titles_a == {"Для всех", "Только A"}
    assert titles_b == {"Для всех", "Только B"}


def test_legacy_tplan_without_athlete_fields():
    demo = Path(__file__).resolve().parents[1] / "demo" / "personal_recomp_july2026.tplan"
    if not demo.exists():
        return
    data = json.loads(demo.read_text(encoding="utf-8"))
    plan = TrainingPlan.from_dict(data)
    assert plan.athletes == []
    for ex in exercises_for_athlete(plan, "any"):
        assert ex.assigned_to_all is True


def test_workout_assignment_serializes():
    w = Workout(title="W", assigned_to_all=False, assigned_athlete_ids=["x"])
    d = w.to_dict()
    w2 = Workout.from_dict(d)
    assert w2.assigned_to_all is False
    assert w2.assigned_athlete_ids == ["x"]
    assert w2.visible_to_athlete("x") is True
    assert w2.visible_to_athlete("y") is False
