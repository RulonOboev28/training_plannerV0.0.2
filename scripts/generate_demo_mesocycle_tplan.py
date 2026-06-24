"""Генерация демонстрационного .tplan — мезоцикл «Объём → скорость + техника»."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import (
    AnnualPlan,
    Connection,
    CycleType,
    Exercise,
    ExerciseType,
    Macrocycle,
    Mesocycle,
    Microcycle,
    TrainingPlan,
    Workout,
)


def ex(
    title: str,
    *,
    etype: ExerciseType = ExerciseType.ENDURANCE,
    duration: int = 0,
    volume_km: float = 0.0,
    intensity: int = 0,
    hr_zone: str = "",
    sets: int = 0,
    reps: int = 0,
    rest: int = 0,
    equipment: str = "",
    notes: str = "",
) -> Exercise:
    return Exercise(
        title=title,
        exercise_type=etype,
        duration_minutes=duration,
        volume_km=volume_km,
        intensity_percent=intensity,
        hr_zone=hr_zone,
        sets=sets,
        reps=reps,
        rest_seconds=rest,
        equipment=equipment,
        notes=notes,
    )


def warmup() -> list[Exercise]:
    return [
        ex("Лёгкий бег / ходьба", etype=ExerciseType.RECOVERY, duration=8, hr_zone="до 120"),
        ex("Суставная гимнастика", etype=ExerciseType.RECOVERY, duration=5,
           notes="Шея, плечи, локти, бёдра, колени, голеностоп"),
        ex("Динамическая растяжка", etype=ExerciseType.RECOVERY, duration=5,
           notes="Махи ногами, наклоны"),
    ]


def spec_warmup(accel_count: int = 2) -> list[Exercise]:
    return [
        ex("Беговые упражнения", etype=ExerciseType.TECHNICAL, duration=7,
           notes="Высокий подъём бедра, захват, выпрыгивания"),
        ex("Имитация лыжного хода", etype=ExerciseType.TECHNICAL, duration=5,
           notes="Классика и конёк на месте"),
        ex("Ускорения-разминки", etype=ExerciseType.SPEED, sets=accel_count, reps=1,
           duration=1, rest=60, notes="10–15 сек, полное восстановление"),
    ]


def cooldown() -> Exercise:
    return ex("Заминка", etype=ExerciseType.RECOVERY, duration=8,
              notes="Спокойный бег / катание / вело, снижение пульса")


def stretch() -> Exercise:
    return ex("Растяжка и восстановление", etype=ExerciseType.RECOVERY, duration=12,
              notes="Задняя поверхность бедра, квадрицепс, икры, ягодицы, поясница, плечи")


def ofp(sets_pull: int = 4, sets_push: int = 4) -> list[Exercise]:
    return [
        ex("Подтягивания", etype=ExerciseType.STRENGTH, sets=sets_pull, reps=12, rest=60),
        ex("Отжимания", etype=ExerciseType.STRENGTH, sets=sets_push, reps=15, rest=60),
        ex("Скручивания на пресс", etype=ExerciseType.STRENGTH, sets=3, reps=15, rest=45),
        ex("Обратные разведения", etype=ExerciseType.STRENGTH, sets=3, reps=12, rest=45,
           notes="Укрепление спины и плечевого пояса"),
    ]


def chain(items: list) -> None:
    for i in range(len(items) - 1):
        items[i].connections.append(Connection(target_id=items[i + 1].id))


def layout_siblings(items: list, x0: float = 0, y0: float = 0, dx: float = 180) -> None:
    for i, item in enumerate(items):
        item.pos_x = x0 + i * dx
        item.pos_y = y0


def run_km(minutes: int) -> float:
    return round(minutes / 9, 1)


def roller_km(minutes: int) -> float:
    return round(minutes / 5, 1)


def bike_km(minutes: int) -> float:
    return round(minutes / 3, 1)


# ── Определения основных частей по дням ─────────────────────────────────────

WEEK1 = [
    ("Пн — активное восстановление", ExerciseType.RECOVERY, [
        ex("Лёгкий кросс или плавание", etype=ExerciseType.RECOVERY, duration=40, hr_zone="120–125"),
        ex("Лёгкое ОФП с собственным весом", etype=ExerciseType.STRENGTH, duration=20,
           notes="Без ускорений, без закисления"),
    ]),
    ("Вт — объёмный кросс", ExerciseType.ENDURANCE, [
        ex("Равномерный бег", duration=90, hr_zone="120–130",
           notes="Слабопересечёнка, подъёмы без ускорения"),
    ]),
    ("Ср — роллеры + техника", ExerciseType.TECHNICAL, [
        ex("Роллеры: классика / конёк", duration=90, hr_zone="120–130", equipment="Лыжероллеры",
           notes="Низкий темп, медленные тренировочные роллеры"),
        ex("Катание без палок", etype=ExerciseType.TECHNICAL, duration=10),
        ex("Double poling (на руках)", etype=ExerciseType.TECHNICAL, duration=10),
        ex("Ускорения на роллерах", etype=ExerciseType.SPEED, sets=4, duration=1, rest=900,
           notes="4×20 сек, раз в 15–20 мин"),
    ]),
    ("Чт — вело + ОФП", ExerciseType.STRENGTH, [
        ex("Велосипед по равнине", duration=60, hr_zone="120–130", equipment="Велосипед"),
        *ofp(4, 4),
    ]),
    ("Пт — объёмный кросс с рельефом", ExerciseType.ENDURANCE, [
        ex("Кросс с умеренным рельефом", duration=90, hr_zone="120–130",
           notes="Подъёмы шагом с палками — шаговая имитация"),
    ]),
    ("Сб — роллеры + техника + ОФП", ExerciseType.TECHNICAL, [
        ex("Роллеры: двухшаг и конёк", duration=90, hr_zone="120–130", equipment="Лыжероллеры",
           notes="Акцент на технику"),
        ex("Ускорения на роллерах", etype=ExerciseType.SPEED, sets=5, duration=1, rest=900,
           notes="5×15 сек"),
        *ofp(3, 3),
    ]),
    ("Вс — длительный кросс", ExerciseType.ENDURANCE, [
        ex("Длительный кросс", duration=120, hr_zone="120–130",
           notes="Все подъёмы — шаговая имитация с палками"),
    ]),
]

WEEK2 = [
    ("Пн — восстановление + мобility", ExerciseType.RECOVERY, [
        ex("Лёгкий кросс", duration=30, hr_zone="120–125"),
        ex("Растяжка / йога", etype=ExerciseType.RECOVERY, duration=15),
        ex("Лёгкое ОФП", etype=ExerciseType.STRENGTH, duration=15),
    ]),
    ("Вт — объёмный кросс", ExerciseType.ENDURANCE, [
        ex("Равномерный бег", duration=105, hr_zone="120–130"),
    ]),
    ("Ср — роллеры + ускорения", ExerciseType.SPEED, [
        ex("Роллеры равномерно", duration=105, hr_zone="120–130", equipment="Лыжероллеры"),
        ex("Ускорения на роллерах", etype=ExerciseType.SPEED, sets=6, duration=1, rest=720,
           notes="6×20–30 сек, каждые 10–12 мин"),
    ]),
    ("Чт — вело + ОФП", ExerciseType.STRENGTH, [
        ex("Велосипед", duration=75, hr_zone="120–130", equipment="Велосипед"),
        *ofp(4, 4),
    ]),
    ("Пт — кросс с рельефом", ExerciseType.TEMPO, [
        ex("Кросс с подъёмами", duration=105, hr_zone="120–140",
           notes="Подъёмы шагом; 3×1 мин умеренно быстрый подъём"),
        ex("Темповые подъёмы", etype=ExerciseType.TEMPO, sets=3, duration=1, rest=180),
    ]),
    ("Сб — роллеры + ОФП", ExerciseType.TECHNICAL, [
        ex("Роллеры: бесшажный ход", duration=105, hr_zone="120–130", equipment="Лыжероллеры",
           notes="Отработка бесшажных элементов на ровном"),
        ex("Ускорения на роллерах", etype=ExerciseType.SPEED, sets=6, duration=1, rest=720,
           notes="6×20 сек"),
        *ofp(4, 4),
    ]),
    ("Вс — длительный кросс с имитацией", ExerciseType.ENDURANCE, [
        ex("Длительный кросс", duration=135, hr_zone="120–130",
           notes="Шаговая имитация; на 2–3 подъёмах — прыжковая имитация до 1 мин"),
        ex("Прыжковая имитация в подъём", etype=ExerciseType.TECHNICAL, sets=3, duration=1,
           notes="Не более 1 мин на подъём"),
    ]),
]

WEEK3 = [
    ("Пн — лёгкое восстановление", ExerciseType.RECOVERY, [
        ex("Лёгкий кросс", duration=45, hr_zone="120–125"),
        ex("Растяжка", etype=ExerciseType.RECOVERY, duration=15),
    ]),
    ("Вт — объёмный кросс", ExerciseType.ENDURANCE, [
        ex("Кросс по рельефу", duration=120, hr_zone="120–130",
           notes="Большие и средние подъёмы, без сильного закисления"),
    ]),
    ("Ср — роллеры: скорость", ExerciseType.SPEED, [
        ex("Роллеры спокойно", duration=120, hr_zone="120–130", equipment="Лыжероллеры",
           notes="Между ускорениями — спокойное катание"),
        ex("Мощные ускорения", etype=ExerciseType.SPEED, sets=9, duration=1, rest=720,
           intensity=95, notes="8–10×20–40 сек, акцент на мощность отталкивания"),
    ]),
    ("Чт — вело + ОФП", ExerciseType.STRENGTH, [
        ex("Велосипед", duration=90, hr_zone="120–130", equipment="Велосипед"),
        *ofp(5, 5),
    ]),
    ("Пт — объёмный кросс", ExerciseType.ENDURANCE, [
        ex("Равномерный кросс", duration=120, hr_zone="120–130"),
    ]),
    ("Сб — роллеры + ОФП + скорость", ExerciseType.SPEED, [
        ex("Роллеры", duration=90, hr_zone="120–130", equipment="Лыжероллеры"),
        ex("Ускорения на роллерах", etype=ExerciseType.SPEED, sets=6, duration=1, rest=720,
           notes="6×30 сек"),
        *ofp(5, 5),
    ]),
    ("Вс — длительный кросс с имитацией", ExerciseType.ENDURANCE, [
        ex("Длительный кросс", duration=120, hr_zone="120–130",
           notes="Шаговая имитация; на крутых участках — прыжковая имитация ≤1 мин"),
        ex("Прыжковая имитация в подъём", etype=ExerciseType.TECHNICAL, sets=4, duration=1),
    ]),
]

WEEK4 = [
    ("Пн — восстановление", ExerciseType.RECOVERY, [
        ex("Лёгкий кросс / плавание", duration=40, hr_zone="120–125"),
        ex("Растяжка", etype=ExerciseType.RECOVERY, duration=15),
    ]),
    ("Вт — объёмный кросс", ExerciseType.ENDURANCE, [
        ex("Лёгкий кросс", duration=90, hr_zone="120–130", notes="Разгрузочная неделя"),
    ]),
    ("Ср — роллеры: техника", ExerciseType.TECHNICAL, [
        ex("Роллеры низкий темп", duration=90, hr_zone="120–125", equipment="Лыжероллеры",
           notes="Закрепление техники"),
        ex("Ускорения (минимум скорости)", etype=ExerciseType.SPEED, sets=4, duration=1,
           rest=900, notes="4×20 сек"),
    ]),
    ("Чт — вело + лёгкое ОФП", ExerciseType.STRENGTH, [
        ex("Велосипед", duration=60, hr_zone="120–130", equipment="Велосипед"),
        *ofp(3, 3),
    ]),
    ("Пт — кросс", ExerciseType.ENDURANCE, [
        ex("Спокойный кросс", duration=90, hr_zone="120–130"),
    ]),
    ("Сб — роллеры", ExerciseType.TECHNICAL, [
        ex("Роллеры: техника", duration=90, hr_zone="120–130", equipment="Лыжероллеры"),
        ex("Ускорения", etype=ExerciseType.SPEED, sets=3, duration=1, rest=900,
           notes="3×20 сек"),
    ]),
    ("Вс — умеренный длинный кросс", ExerciseType.ENDURANCE, [
        ex("Кросс с шаговой имитацией", duration=105, hr_zone="120–130",
           notes="Подъёмы — шаговая имитация с палками"),
    ]),
]

MICROCYCLES = [
    ("МК1 — Втягивание", CycleType.INTRO, 7, WEEK1,
     "Втягивающий микроцикл. ~10 ч/нед. Акцент: техника, низкий пульс."),
    ("МК2 — Наращивание объёма", CycleType.BASE, 7, WEEK2,
     "Базовый микроцикл. ~11–12 ч/нед. Больше часов, первые темповые вставки."),
    ("МК3 — Объём + скорость", CycleType.CONTROL, 7, WEEK3,
     "Контрольно-подготовительный. ~12–13 ч/нед. Пик мезоцикла."),
    ("МК4 — Разгрузка", CycleType.RECOVERY, 7, WEEK4,
     "Восстановительный. ~9–10 ч/нед. Сохранение техники и минимума скорости."),
]


def build_workout(title: str, wtype: ExerciseType, main_exercises: list[Exercise]) -> Workout:
    accel = 3 if "скорост" in title.lower() or wtype == ExerciseType.SPEED else 2
    exercises = warmup() + spec_warmup(accel) + main_exercises + [cooldown(), stretch()]
    chain(exercises)
    total = sum(e.duration_minutes for e in exercises)
    return Workout(title=title, workout_type=wtype, duration_minutes=total, exercises=exercises)


def build_microcycle(title: str, ctype: CycleType, days: int, week_def: list, notes: str) -> Microcycle:
    workouts = [build_workout(day_title, wtype, mains) for day_title, wtype, mains in week_def]
    chain(workouts)
    layout_siblings(workouts, dx=220)
    for i, w in enumerate(workouts):
        layout_siblings(w.exercises, x0=20, y0=30 + i * 10, dx=160)
    return Microcycle(
        title=title,
        cycle_type=ctype,
        duration_days=days,
        notes=notes,
        workouts=workouts,
    )


def _apply_volumes(element) -> None:
    from core.models import Exercise, get_children

    if isinstance(element, Exercise):
        if element.volume_km > 0 or element.duration_minutes <= 0:
            return
        text = f"{element.title} {element.notes} {element.equipment}".lower()
        if element.equipment == "Лыжероллеры" or "роллер" in text:
            if element.duration_minutes >= 10:
                element.volume_km = roller_km(element.duration_minutes)
        elif element.equipment == "Велосипед" or "вело" in text:
            if element.duration_minutes >= 15:
                element.volume_km = bike_km(element.duration_minutes)
        elif any(x in text for x in ("кросс", "бег", "run", "пробеж")):
            if element.duration_minutes >= 20:
                element.volume_km = run_km(element.duration_minutes)
        return
    for child in get_children(element):
        _apply_volumes(child)


def build_plan() -> TrainingPlan:
    microcycles = [
        build_microcycle(title, ctype, days, week, notes)
        for title, ctype, days, week, notes in MICROCYCLES
    ]
    chain(microcycles)
    layout_siblings(microcycles, dx=1700)

    meso = Mesocycle(
        title="Объём → скорость + техника",
        cycle_type=CycleType.CONTROL,
        duration_weeks=4,
        notes=(
            "Лыжные гонки, летне-осенний период. Любитель 1–2 года. "
            "Цель: объёмная база + скоростная работа + техника на роллерах. "
            "Пульс объём: 120–130; темп: 140–150. Ежедневные тренировки."
        ),
        microcycles=microcycles,
        pos_x=400,
        pos_y=200,
    )

    macro = Macrocycle(
        title="Демо-блок",
        duration_months=1,
        mesocycles=[meso],
        notes="Обёртка для импорта мезоцикла в конструктор.",
        pos_x=200,
        pos_y=100,
    )

    annual = AnnualPlan(
        title="Демо: мезоцикл лыжных гонок",
        year=2026,
        sport_type="Лыжные гонки",
        macrocycles=[macro],
        notes="Демонстрационный план для публичной презентации приложения.",
    )

    plan = TrainingPlan(annual=annual)
    _apply_volumes(plan.annual)
    return plan


def main() -> None:
    plan = build_plan()
    desktop = Path.home() / "Desktop"
    out = desktop / "mesocycle_obem_skorost_tehnika.tplan"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"Saved: {out}")
    print(f"Microcycles: {len(plan.annual.macrocycles[0].mesocycles[0].microcycles)}")
    workouts = sum(
        len(m.workouts)
        for m in plan.annual.macrocycles[0].mesocycles[0].microcycles
    )
    exercises = sum(
        len(w.exercises)
        for m in plan.annual.macrocycles[0].mesocycles[0].microcycles
        for w in m.workouts
    )
    print(f"Workouts: {workouts}, Exercises: {exercises}")


if __name__ == "__main__":
    main()
