"""Генерация .tplan из «Персональной программы тренировок» (блокнот на рабочем столе).

Два микроцикла (неделя 1 и неделя 2) в одном мезоцикле, даты с 6 июля 2026.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models import (  # noqa: E402
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

# Размеры плиток совпадают с ui/canvas/nodes.py (обыный пресет).
TILE_W = 300.0
TILE_H = 100.0
TILE_GAP = 50.0
BLOCK_GAP = 140.0  # дополнительный зазор между логическими блоками

PLAN_START = "2026-07-06"
MC1_DATES = ("2026-07-06", "2026-07-08", "2026-07-10")
MC2_DATES = ("2026-07-13", "2026-07-15", "2026-07-17")


@dataclass
class ExSpec:
    title: str
    sets: int = 0
    reps: int = 0
    rep_range: str = ""
    rest_seconds: int = 0
    notes: str = ""
    equipment: str = ""
    exercise_type: ExerciseType = ExerciseType.STRENGTH


def _chain(items: list, kind: str = "sequence") -> None:
    for i in range(len(items) - 1):
        items[i].connections.append(
            Connection(target_id=items[i + 1].id, kind=kind)
        )


def _layout_column(items: list, x: float, start_y: float = 0.0) -> None:
    """Колонка: плитки друг под другом, стрелки сверху вниз."""
    y = start_y
    for item in items:
        item.pos_x = x
        item.pos_y = y
        y += TILE_H + TILE_GAP


def _layout_row(items: list, x: float, y: float = 0.0) -> float:
    """Ряд: плитки слева направо. Возвращает x после последней плитки."""
    for item in items:
        item.pos_x = x
        item.pos_y = y
        x += TILE_W + TILE_GAP
    return x


def _layout_row_with_blocks(items: list, start_x: float = 0.0, y: float = 0.0) -> None:
    """Горизонтальный ряд для уровней тренировок / микроциклов."""
    _layout_row(items, start_x, y)


def _connect_blocks(blocks: list[list]) -> None:
    """Связать блоки: внутри колонки — сверху вниз, между блоками — последний→первый."""
    prev_last = None
    for block in blocks:
        if not block:
            continue
        _chain(block)
        if prev_last is not None:
            prev_last.connections.append(Connection(target_id=block[0].id))
        prev_last = block[-1]


def _layout_workout_exercises(
    warmup: list[Exercise],
    main: list[Exercise],
    press: list[Exercise],
) -> list[Exercise]:
    """Разминка — колонка; основная часть и пресс — горизонтально с отступами."""
    _layout_column(warmup, x=0.0)

    x = TILE_W + BLOCK_GAP
    x = _layout_row(main, x, y=0.0)

    if press:
        x += BLOCK_GAP - TILE_GAP
        _layout_row(press, x, y=0.0)

    _connect_blocks([warmup, main, press])
    return warmup + main + press


def _ex(spec: ExSpec) -> Exercise:
    notes = spec.notes
    if spec.rep_range:
        range_line = f"Диапазон: {spec.rep_range} повторений."
        notes = f"{range_line}\n{notes}" if notes else range_line
    return Exercise(
        title=spec.title,
        exercise_type=spec.exercise_type,
        duration_minutes=0,
        sets=spec.sets,
        reps=spec.reps,
        rest_seconds=spec.rest_seconds,
        notes=notes.strip(),
        equipment=spec.equipment,
    )


def _warmup_block() -> list[Exercise]:
    return [
        Exercise(
            title="Суставная гимнастика",
            exercise_type=ExerciseType.TECHNICAL,
            duration_minutes=0,
            notes=(
                "По 10 вращений: шея, плечи, локти, кисти, таз, колени, голеностоп."
            ),
        ),
        _ex(ExSpec("Отжимания (разминка)", 2, 10, equipment="собственный вес")),
        _ex(ExSpec("Приседания (разминка)", 2, 15, equipment="собственный вес")),
        _ex(
            ExSpec(
                "Подтягивание лопатками",
                2,
                10,
                notes="Не подтягиваясь полностью.",
            )
        ),
        Exercise(
            title="Планка (разминка)",
            exercise_type=ExerciseType.TECHNICAL,
            duration_minutes=0,
            sets=1,
            reps=0,
            notes="30 секунд.",
        ),
        _ex(ExSpec("Разведение резинки", 2, 20, equipment="резинка")),
        Exercise(
            title="Разминочный подход 1-го упражнения",
            exercise_type=ExerciseType.TECHNICAL,
            duration_minutes=0,
            notes=(
                "Пример: рабочий вес 20 кг → 10 кг×10, 15 кг×5, затем рабочие подходы."
            ),
        ),
    ]


def _build_workout(
    title: str,
    main_specs: list[ExSpec],
    press_specs: list[ExSpec],
    workout_notes: str,
    start_date: str,
) -> Workout:
    warmup = _warmup_block()
    main = [_ex(s) for s in main_specs]
    press = [_ex(s) for s in press_specs]
    blocks = _layout_workout_exercises(warmup, main, press)

    workout = Workout(
        title=title,
        workout_type=ExerciseType.STRENGTH,
        duration_minutes=0,
        exercises=blocks,
        notes=workout_notes,
        start_date=start_date,
    )
    for ex in workout.exercises:
        ex.scheduled_date = start_date
    return workout


# ── Неделя 1 (вводная) ─────────────────────────────────────────────────────

WEEK1_A: list[ExSpec] = [
    ExSpec(
        "Подтягивания широким хватом",
        3,
        8,
        "6–8",
        120,
        "Да, начинаем не с груди. Это сделано намеренно: подтягивания отлично "
        "разогревают плечевой пояс и улучшают стабильность перед жимовыми упражнениями. "
        "Если легко — используй рюкзак с весом.",
        "турник",
    ),
    ExSpec(
        "Жим гантелей лёжа на полу",
        4,
        10,
        "8–10",
        120,
        "Главное базовое упражнение. Медленное опускание. "
        "Полностью не расслабляй руки внизу.",
        "гантели",
    ),
    ExSpec(
        "Отжимания с резинкой",
        4,
        15,
        "10–15",
        90,
        "Резинку заводишь за спину. Последний подход — почти до отказа.",
        "резинка",
    ),
    ExSpec(
        "Разведения гантелей лёжа на полу",
        3,
        15,
        "12–15",
        60,
        "Да, амплитуда меньше, чем на скамье. Но отлично работает верхняя часть грудных. "
        "Без больших весов. Главное — растянуть грудь.",
        "гантели",
    ),
    ExSpec(
        "Отжимания на брусьях",
        3,
        12,
        "8–12",
        120,
        "С небольшим наклоном вперёд. Если станет легко — добавляем рюкзак.",
        "брусья",
    ),
    ExSpec(
        "Французский жим одной гантелью",
        3,
        12,
        "10–12",
        60,
        "Из-за головы. Сидя.",
        "гантель",
    ),
    ExSpec(
        "Подъём гантелей перед собой",
        3,
        15,
        "12–15",
        60,
        "Передняя дельта.",
        "гантели",
    ),
]

WEEK1_A_PRESS: list[ExSpec] = [
    ExSpec(
        "Подъём ног в висе",
        3,
        15,
        "12–15",
        60,
        "Не раскачиваться.",
        "турник",
    ),
    ExSpec(
        "Планка",
        3,
        0,
        "",
        60,
        "3 подхода по 45–60 секунд.",
    ),
]

WEEK1_B: list[ExSpec] = [
    ExSpec(
        "Подтягивания",
        4,
        0,
        "максимум −2",
        120,
        "Не до отказа — оставляй 2 повторения в запасе.",
        "турник",
    ),
    ExSpec(
        "Тяга одной гантели",
        4,
        12,
        "10–12",
        90,
        "Опора рукой и коленом на диван. Если диван слишком мягкий — "
        "используй два устойчивых стула. Каждая рука.",
        "гантель, диван/стулья",
    ),
    ExSpec(
        "Тяга гантелей к поясу в наклоне",
        4,
        10,
        "8–10",
        120,
        "Можно выполнять с двумя гантелями одновременно. "
        "Либо одной тяжёлой (22,5 кг).",
        "гантели",
    ),
    ExSpec(
        "Тяга резинки сверху вниз",
        3,
        15,
        "15",
        60,
        "Имитация вертикального блока. Очень медленно.",
        "резинка",
    ),
    ExSpec(
        "Face Pull резинкой",
        3,
        20,
        "15–20",
        60,
        "Одно из лучших упражнений.",
        "резинка",
    ),
    ExSpec(
        "Подъём гантелей на бицепс",
        3,
        12,
        "10–12",
        60,
        "Попеременно.",
        "гантели",
    ),
    ExSpec(
        "Молотки",
        3,
        12,
        "12",
        60,
        "",
        "гантели",
    ),
]

WEEK1_B_PRESS: list[ExSpec] = [
    ExSpec("Русские повороты", 3, 20, "20", 45, "", "собственный вес"),
    ExSpec(
        "Боковая планка",
        2,
        0,
        "",
        45,
        "2×40 секунд на каждую сторону.",
    ),
]

WEEK1_C: list[ExSpec] = [
    ExSpec(
        "Приседания с двумя гантелями",
        4,
        12,
        "10–12",
        120,
        "Если веса не хватает — замедляй опускание до 3–4 секунд "
        "и делай паузу внизу на 1 секунду.",
        "гантели",
    ),
    ExSpec(
        "Румынская тяга с гантелями",
        4,
        10,
        "8–10",
        120,
        "Следи за нейтральным положением спины, "
        "движение начинается с отведения таза назад.",
        "гантели",
    ),
    ExSpec(
        "Болгарские сплит-приседания",
        3,
        12,
        "10–12",
        90,
        "Задняя нога на диване. На каждую ногу. "
        "Отлично компенсирует ограниченный вес гантелей.",
        "гантели, диван",
    ),
    ExSpec(
        "Подъёмы на носки стоя",
        4,
        20,
        "15–20",
        60,
        "С гантелями в руках. В верхней точке задержка 1–2 секунды.",
        "гантели",
    ),
    ExSpec(
        "Жим гантелей стоя",
        4,
        10,
        "8–10",
        120,
        "Не прогибайся в пояснице, напряги пресс и ягодицы.",
        "гантели",
    ),
    ExSpec(
        "Разведения гантелей в стороны",
        3,
        15,
        "12–15",
        60,
        "Поднимай локти чуть выше кистей, не поднимай плечи к ушам.",
        "гантели",
    ),
    ExSpec(
        "Отжимания узким хватом",
        3,
        0,
        "почти до отказа",
        90,
        "Дополнительная нагрузка на грудь и трицепс.",
        "собственный вес",
    ),
    ExSpec(
        "Сгибания рук с резинкой (добивка)",
        2,
        20,
        "15–20",
        45,
        "До ощущения хорошего жжения, но без нарушения техники.",
        "резинка",
    ),
]

WEEK1_C_PRESS: list[ExSpec] = [
    ExSpec(
        "Скручивания с медленным негативом",
        3,
        20,
        "15–20",
        45,
        "Опускание корпуса — 3 секунды.",
    ),
    ExSpec(
        "Подъём коленей в висе",
        3,
        15,
        "12–15",
        60,
        "Без раскачивания, концентрируйся на работе пресса.",
        "турник",
    ),
]

# ── Неделя 2 (TUT, больше повторений) ───────────────────────────────────────

WEEK2_A: list[ExSpec] = [
    ExSpec(
        "Подтягивания",
        4,
        8,
        "8",
        120,
        "Последний подход — максимум без нарушения техники.",
        "турник",
    ),
    ExSpec(
        "Жим гантелей лёжа",
        4,
        12,
        "10–12",
        120,
        "Опускаем вес на 10–15%. Опускание 3 секунды.",
        "гантели",
    ),
    ExSpec(
        "Отжимания с резинкой",
        4,
        15,
        "12–15",
        90,
        "Последний подход до технического отказа.",
        "резинка",
    ),
    ExSpec(
        "Сведение гантелей лёжа",
        3,
        15,
        "15",
        60,
        "В верхней точке не соединять гантели. Постоянное напряжение.",
        "гантели",
    ),
    ExSpec(
        "Брусья",
        3,
        12,
        "10–12",
        120,
        "Медленный негатив.",
        "брусья",
    ),
    ExSpec(
        "Французский жим",
        3,
        15,
        "12–15",
        60,
        "В последнем подходе сразу после отказа берёшь более лёгкую гантель "
        "и выполняешь ещё 6–8 повторений. (Первый дроп-сет.)",
        "гантель",
    ),
    ExSpec(
        "Подъём перед собой",
        3,
        15,
        "15",
        60,
        "Без читинга.",
        "гантели",
    ),
]

WEEK2_A_PRESS: list[ExSpec] = [
    ExSpec(
        "Подъём ног к турнику",
        4,
        12,
        "12",
        60,
        "",
        "турник",
    ),
    ExSpec(
        "Планка",
        1,
        0,
        "",
        0,
        "1 подход максимум времени. Запиши результат — будем улучшать.",
    ),
]

WEEK2_B: list[ExSpec] = [
    ExSpec(
        "Подтягивания",
        5,
        0,
        "максимум −1",
        120,
        "5 подходов по максимум −1 повторение.",
        "турник",
    ),
    ExSpec(
        "Тяга одной рукой",
        4,
        12,
        "12",
        90,
        "В верхней точке удержание 1 секунда.",
        "гантель",
    ),
    ExSpec(
        "Тяга гантелей",
        3,
        15,
        "12–15",
        90,
        "Опускание 3 секунды.",
        "гантели",
    ),
    ExSpec(
        "Тяга резинки",
        4,
        15,
        "15",
        60,
        "Максимально растягивай широчайшие.",
        "резинка",
    ),
    ExSpec(
        "Face Pull",
        4,
        20,
        "20",
        60,
        "Одно из самых важных упражнений программы. Не пропускай.",
        "резинка",
    ),
    ExSpec(
        "Подъёмы на бицепс",
        4,
        12,
        "12",
        60,
        "После последнего подхода сразу без отдыха делаем молотки.",
        "гантели",
    ),
    ExSpec(
        "Молотки",
        1,
        0,
        "до отказа",
        0,
        "Супerset после подъёмов на бицепс — до отказа.",
        "гантели",
    ),
]

WEEK2_B_PRESS: list[ExSpec] = [
    ExSpec("Русские повороты", 4, 25, "25", 45),
    ExSpec("Боковая планка", 3, 0, "", 45, "3×45 секунд."),
]

WEEK2_C: list[ExSpec] = [
    ExSpec(
        "Приседания",
        4,
        15,
        "15",
        120,
        "Вес немного легче. Очень медленно.",
        "гантели",
    ),
    ExSpec(
        "Румынская тяга",
        4,
        12,
        "12",
        120,
        "Пауза 1 секунда в растянутом положении.",
        "гантели",
    ),
    ExSpec(
        "Болгарские приседы",
        3,
        12,
        "12",
        90,
        "Последний подход — без веса. До жжения.",
        "гантели, диван",
    ),
    ExSpec(
        "Подъём на носки",
        5,
        20,
        "20",
        60,
        "Пауза сверху 2 секунды.",
        "гантели",
    ),
    ExSpec(
        "Жим гантелей вверх",
        4,
        12,
        "10–12",
        120,
        "Последний подход — дроп-сет.",
        "гантели",
    ),
    ExSpec(
        "Разведения",
        4,
        15,
        "15",
        60,
        "Очень медленно.",
        "гантели",
    ),
    ExSpec(
        "Отжимания",
        2,
        0,
        "до отказа",
        90,
        "2 подхода до отказа.",
        "собственный вес",
    ),
    ExSpec(
        "Бицепс резинкой",
        2,
        20,
        "20",
        45,
        "",
        "резинка",
    ),
]

WEEK2_C_PRESS: list[ExSpec] = [
    ExSpec("Скручивания", 4, 20, "20", 45),
    ExSpec("Подъём ног", 3, 15, "15", 60, "", "турник"),
]


def _microcycle(
    title: str,
    cycle_type: CycleType,
    notes: str,
    days: list[tuple[str, list[ExSpec], list[ExSpec], str]],
    dates: tuple[str, str, str],
    start_date: str,
    end_date: str,
) -> Microcycle:
    workouts: list[Workout] = []
    for (day_title, main, press, day_notes), date in zip(days, dates):
        w = _build_workout(day_title, main, press, day_notes, date)
        workouts.append(w)

    _layout_row_with_blocks(workouts)
    _chain(workouts)

    return Microcycle(
        title=title,
        cycle_type=cycle_type,
        duration_days=7,
        workouts=workouts,
        notes=notes,
        start_date=start_date,
        end_date=end_date,
    )


def build_plan() -> TrainingPlan:
    mc1_days = [
        (
            "День А — Грудь + Трицепс + Передняя дельта",
            WEEK1_A,
            WEEK1_A_PRESS,
            "Неделя №1 · вводная. Интенсивность: 1–2 повторения до отказа. "
            "Темп 2–0–2. Отдых: тяжёлые 2 мин, средние 90 сек, изоляция 45–60 сек.",
        ),
        (
            "День B — Спина + Бицепс + Задняя дельта",
            WEEK1_B,
            WEEK1_B_PRESS,
            "Неделя №1 · вводная. Не стремись сразу увеличивать веса — "
            "восстанови технику и почувствуй работу мышц.",
        ),
        (
            "День C — Ноги + Плечи + Добивка груди и рук",
            WEEK1_C,
            WEEK1_C_PRESS,
            "Неделя №1 · вводная. Ноги поддерживают гормональный фон и "
            "снижают риск дисбалансов.",
        ),
    ]

    mc2_days = [
        (
            "День А — Грудь + Трицепс + Передняя дельта",
            WEEK2_A,
            WEEK2_A_PRESS,
            "Неделя №2 · диапазон 10–15 повторений, вес −10–15%. "
            "В последних подходах базовых упражнений можно подходить к отказу.",
        ),
        (
            "День B — Спина + Бицепс",
            WEEK2_B,
            WEEK2_B_PRESS,
            "Неделя №2 · увеличение времени под нагрузкой (TUT). "
            "Face Pull — не пропускать.",
        ),
        (
            "День C — Ноги + Плечи + Дополнительная грудь",
            WEEK2_C,
            WEEK2_C_PRESS,
            "Неделя №2 · дроп-сеты и медленные негативы при ограниченном инвентаре.",
        ),
    ]

    mc1 = _microcycle(
        "Микроцикл 1 — Неделя №1 (вводная)",
        CycleType.INTRO,
        "Вводный микроцикл. Цель — привычка и техника, не максимум. "
        "Силовые: 6, 8, 10 июля. Воскресенье 12 июля — отдых. "
        "Между силовыми днями — велосипед (вт, чт, сб) по программе блокнота.",
        mc1_days,
        MC1_DATES,
        "2026-07-06",
        "2026-07-12",
    )

    mc2 = _microcycle(
        "Микроцикл 2 — Неделя №2 (TUT)",
        CycleType.BASE,
        "Второй микроцикл. Больше повторений, контроль движения, памп. "
        "Силовые: 13, 15, 17 июля. Суббота 18 и воскресенье 19 июля — выходные.",
        mc2_days,
        MC2_DATES,
        "2026-07-13",
        "2026-07-19",
    )

    _layout_row_with_blocks([mc1, mc2])
    _chain([mc1, mc2])

    meso = Mesocycle(
        title="Рекомпозиция — вводный блок (2 недели)",
        cycle_type=CycleType.INTRO,
        duration_weeks=2,
        microcycles=[mc1, mc2],
        start_date="2026-07-06",
        end_date="2026-07-19",
        notes=(
            "Персональная программа v1.0. 24 года, 189 см, 86 кг. "
            "Цель: снижение жира до 14–16% с набором мышечной массы. "
            "Частота: Пн/Ср/Пт — силовая; Вт/Чт/Сб — велосипед 40–60 мин, пульс 120–140; "
            "Вс — отдых. Разминка 10 мин + основная часть 60–75 мин + пресс 10 мин. "
            "Белок ≈170 г/день, вода 3 л, креатин 5 г/день, сон 7,5–9 ч. "
            "Прогрессия: верхняя граница повторений во всех подходах → +2 кг. "
            "Цикл рассчитан минимум на 8–12 недель (чередование недель 1 и 2)."
        ),
    )
    meso.pos_x = 0.0
    meso.pos_y = 0.0

    macro = Macrocycle(
        title="Летний блок — рекомпозиция",
        duration_months=1,
        mesocycles=[meso],
        start_date="2026-07-06",
        end_date="2026-07-19",
        notes="Первый мезоцикл программы рекомпозиции тела.",
    )
    macro.pos_x = 0.0
    macro.pos_y = 0.0

    annual = AnnualPlan(
        title="Персональная программа тренировок v1.0",
        year=2026,
        sport_type="Силовой тренинг / домашний зал",
        macrocycles=[macro],
        start_date=PLAN_START,
        notes=(
            "Программа из блокнота «Персональная программа тренировок». "
            "Инвентарь: гантели до 2×12,5 кг, турник, брусья, резинки, диван. "
            "Первые две недели — вводные. Главная задача — регулярность."
        ),
    )

    return TrainingPlan(annual=annual, plan_start_date=PLAN_START)


def main() -> None:
    plan = build_plan()
    data = plan.to_dict()

    out_desktop = Path(r"C:\Users\Rulon Oboev\Desktop\Персональная_программа_тренировок.tplan")
    out_demo = ROOT / "demo" / "personal_recomp_july2026.tplan"

    for path in (out_desktop, out_demo):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    meso = plan.annual.macrocycles[0].mesocycles[0]
    workouts = sum(len(m.workouts) for m in meso.microcycles)
    exercises = sum(
        len(w.exercises)
        for m in meso.microcycles
        for w in m.workouts
    )

    print(f"Сохранено: {out_desktop}")
    print(f"Копия:   {out_demo}")
    print(f"Микроциклов: {len(meso.microcycles)}, тренировок: {workouts}, упражнений: {exercises}")


if __name__ == "__main__":
    main()
