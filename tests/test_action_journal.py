from core.action_journal import ActionJournal, format_entry
from core.models import Exercise, TrainingPlan, Workout, Microcycle, Mesocycle, Macrocycle, AnnualPlan


def _plan_with_workout():
    ex = Exercise(title="Бег", duration_minutes=30)
    w = Workout(title="Тренировка", exercises=[ex], start_date="2026-10-14")
    micro = Microcycle(title="M1", workouts=[w])
    meso = Mesocycle(title="Meso", microcycles=[micro])
    macro = Macrocycle(title="Macro", mesocycles=[meso])
    annual = AnnualPlan(title="Год", macrocycles=[macro])
    plan = TrainingPlan(annual=annual, plan_start_date="2026-01-01")
    return plan, ex, w


def test_journal_edit_shows_calendar_date():
    plan, ex, _w = _plan_with_workout()
    journal = ActionJournal(limit=25)
    journal.record(plan, ("edit", ex.id), hist_index=1)
    entry = journal.entries()[-1]
    assert "упражнение" in entry.text.lower()
    assert entry.calendar_date is not None
    assert format_entry(entry).endswith("2026")
