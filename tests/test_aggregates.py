"""Тесты распределения нагрузки по уровням."""
from core.aggregates import aggregate_sections
from core.models import (
    AnnualPlan, Exercise, ExerciseType, Macrocycle, Mesocycle, Microcycle,
    Workout,
)


def _roller_classic(minutes: int, km: float) -> Exercise:
    return Exercise(
        title="Роллеры классика",
        exercise_type=ExerciseType.TECHNICAL,
        duration_minutes=minutes,
        volume_km=km,
        equipment="Лыжероллеры",
    )


def _run(minutes: int, km: float) -> Exercise:
    return Exercise(
        title="Равномерный кросс",
        exercise_type=ExerciseType.ENDURANCE,
        duration_minutes=minutes,
        volume_km=km,
    )


def test_mesocycle_child_and_modality_breakdown():
    mk1 = Microcycle(
        title="МК1",
        workouts=[
            Workout(
                title="Ср",
                exercises=[_roller_classic(120, 35), _run(60, 10)],
            ),
        ],
    )
    mk2 = Microcycle(
        title="МК2",
        workouts=[
            Workout(
                title="Ср",
                exercises=[_roller_classic(90, 35)],
            ),
        ],
    )
    meso = Mesocycle(title="Мезо", microcycles=[mk1, mk2])
    sections = {s.title: dict(s.rows) for s in aggregate_sections(meso)}

    assert sections["Итого"]["Суммарное время"] == "4.5 ч"
    assert sections["Итого"]["Суммарный объём"] == "80 км"
    assert sections["По микроциклам"]["МК1"] == "3 ч · 45 км"
    assert sections["По микроциклам"]["МК2"] == "1.5 ч · 35 км"
    assert sections["По видам нагрузки"]["Лыжероллеры · классика"] == "3.5 ч · 70 км"
    assert sections["По видам нагрузки"]["Бег"] == "1 ч · 10 км"


def test_workout_shows_exercise_breakdown():
    workout = Workout(
        title="Среда",
        exercises=[
            Exercise(title="Разминка", exercise_type=ExerciseType.RECOVERY, duration_minutes=15),
            _roller_classic(90, 20),
        ],
    )
    sections = {s.title: dict(s.rows) for s in aggregate_sections(workout)}
    assert sections["По упражнениям"]["Разминка"] == "15 мин"
    assert sections["По упражнениям"]["Роллеры классика"] == "1.5 ч · 20 км"


def test_microcycle_per_workout():
    micro = Microcycle(
        title="Неделя 1",
        workouts=[
            Workout(title="Пн", exercises=[_run(40, 6)]),
            Workout(title="Вт", exercises=[_roller_classic(90, 18)]),
        ],
    )
    sections = {s.title: dict(s.rows) for s in aggregate_sections(micro)}
    assert sections["По тренировкам"]["Пн"] == "40 мин · 6 км"
    assert sections["По тренировкам"]["Вт"] == "1.5 ч · 18 км"


def test_annual_macrocycle_breakdown():
    meso = Mesocycle(
        title="М1",
        microcycles=[
            Microcycle(
                title="МК",
                workouts=[Workout(title="День", exercises=[_run(60, 10)])],
            ),
        ],
    )
    macro = Macrocycle(title="Лето", mesocycles=[meso])
    annual = AnnualPlan(title="2026", macrocycles=[macro])
    sections = {s.title: dict(s.rows) for s in aggregate_sections(annual)}
    assert sections["По макроциклам"]["Лето"] == "1 ч · 10 км"


def test_exercise_returns_empty():
    assert aggregate_sections(Exercise(title="Кросс")) == []
