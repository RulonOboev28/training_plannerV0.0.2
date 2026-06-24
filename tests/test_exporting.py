"""Тесты экспорта плана в таблицу и клонирования элементов."""
from core.exporting import HEADER, plan_to_csv, plan_to_rows
from core.models import (
    AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, TrainingPlan,
    Workout, clone_element, get_children,
)


def _make_plan() -> TrainingPlan:
    ex = Exercise(title="Кросс", duration_minutes=40, volume_km=8)
    workout = Workout(title="Утро", exercises=[ex])
    micro = Microcycle(title="Нед.1", workouts=[workout])
    meso = Mesocycle(microcycles=[micro])
    macro = Macrocycle(mesocycles=[meso])
    return TrainingPlan(annual=AnnualPlan(title="Год", macrocycles=[macro]))


def test_plan_to_rows_header_and_content():
    rows = plan_to_rows(_make_plan())
    assert rows[0] == HEADER
    # 6 уровней: годичный план + макро + мезо + микро + тренировка + упражнение
    assert len(rows) == 7
    titles = " ".join(cell for row in rows for cell in row)
    assert "Кросс" in titles
    assert "Год" in titles


def test_plan_to_csv_is_semicolon_separated():
    csv_text = plan_to_csv(_make_plan())
    assert ";" in csv_text
    assert csv_text.strip().splitlines()[0].startswith("Уровень")


def test_clone_element_generates_new_ids():
    workout = Workout(title="Утро", exercises=[Exercise(title="Кросс")])
    copy = clone_element(workout)
    assert copy.id != workout.id
    assert copy.title == workout.title
    orig_child = get_children(workout)[0]
    copy_child = get_children(copy)[0]
    assert orig_child.id != copy_child.id
