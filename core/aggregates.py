"""Сводная статистика и распределение нагрузки по уровням иерархии."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.models import Exercise, ExerciseType, get_children


@dataclass
class _Load:
    minutes: int = 0
    km: float = 0.0
    count: int = 0

    def add_exercise(self, ex: Exercise) -> None:
        self.minutes += ex.duration_minutes
        self.km += ex.volume_km
        self.count += 1

    def add(self, other: "_Load") -> None:
        self.minutes += other.minutes
        self.km += other.km
        self.count += other.count


@dataclass
class StatSection:
    title: str
    rows: List[Tuple[str, str]] = field(default_factory=list)


def _all_exercises(element) -> List[Exercise]:
    if isinstance(element, Exercise):
        return [element]
    out: List[Exercise] = []
    for child in get_children(element):
        out.extend(_all_exercises(child))
    return out


def _fmt_num(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _fmt_duration(minutes: int) -> str:
    if minutes <= 0:
        return ""
    if minutes < 60:
        return f"{minutes} мин"
    hours = minutes / 60.0
    if float(hours).is_integer():
        return f"{int(hours)} ч"
    return f"{_fmt_num(hours)} ч"


def _fmt_load(load: _Load) -> str:
    parts: List[str] = []
    if load.minutes:
        parts.append(_fmt_duration(load.minutes))
    if load.km:
        parts.append(f"{_fmt_num(load.km)} км")
    if load.count and not parts:
        parts.append(f"{load.count} упр.")
    return " · ".join(parts) if parts else "—"


def _text_blob(ex: Exercise) -> str:
    return f"{ex.title} {ex.notes} {ex.equipment}".lower()


def _style_suffix(text: str) -> str:
    if any(x in text for x in ("double poling", "на руках", "дабл")):
        return " · double poling"
    if "без палок" in text:
        return " · без палок"
    if any(x in text for x in ("классик", "classic", "классическ")):
        return " · классика"
    if any(x in text for x in ("конёк", "коньк", "коньков", "skate", "skating")):
        return " · конёк"
    if any(x in text for x in ("бесшаж", "skate ski")):
        return " · бесшажный ход"
    return ""


def _modality_key(ex: Exercise) -> str:
    text = _text_blob(ex)
    style = _style_suffix(text)
    equipment = ex.equipment.strip()

    if equipment:
        return equipment + style

    if "роллер" in text:
        return "Лыжероллеры" + style
    if any(x in text for x in ("вело", "велосипед", "bike", "cycling")):
        return "Велосипед"
    if any(x in text for x in ("плаван", "бассейн", "swim")):
        return "Плавание"
    if any(x in text for x in ("кросс", "бег", "run", "пробеж")):
        return "Бег" + style
    if any(x in text for x in ("лыж", "ski")) and "роллер" not in text:
        return "Лыжи" + style
    if ex.exercise_type == ExerciseType.STRENGTH or any(
        x in text for x in ("офп", "подтяг", "отжим", "пресс", "силов")
    ):
        return "ОФП / силовая"
    if ex.exercise_type == ExerciseType.RECOVERY or any(
        x in text for x in ("растяж", "йога", "восстанов", "мобility", "заминка")
    ):
        return "Восстановление / растяжка"
    if ex.exercise_type == ExerciseType.SPEED:
        return "Скоростная работа" + style
    if ex.exercise_type == ExerciseType.TECHNICAL:
        return "Техническая работа" + style
    if ex.exercise_type == ExerciseType.TEMPO:
        return "Темповая работа" + style
    return ex.exercise_type.value


def _summarize(exercises: List[Exercise]) -> _Load:
    total = _Load()
    for ex in exercises:
        total.add_exercise(ex)
    return total


def _group_by_modality(exercises: List[Exercise]) -> Dict[str, _Load]:
    groups: Dict[str, _Load] = {}
    for ex in exercises:
        key = _modality_key(ex)
        groups.setdefault(key, _Load()).add_exercise(ex)
    return groups


def _group_by_type(exercises: List[Exercise]) -> Dict[ExerciseType, _Load]:
    groups: Dict[ExerciseType, _Load] = {}
    for ex in exercises:
        groups.setdefault(ex.exercise_type, _Load()).add_exercise(ex)
    return groups


def _child_section_title(element) -> str:
    from core.models import (
        AnnualPlan, Exercise, Macrocycle, Mesocycle, Microcycle, Workout,
    )

    child = get_children(element)
    if not child:
        return "По элементам"
    sample = child[0]
    if isinstance(sample, Exercise):
        return "По упражнениям"
    if isinstance(sample, Workout):
        return "По тренировкам"
    if isinstance(sample, Microcycle):
        return "По микроциклам"
    if isinstance(sample, Mesocycle):
        return "По мезоциклам"
    if isinstance(sample, Macrocycle):
        return "По макроциклам"
    if isinstance(element, AnnualPlan):
        return "По макроциклам"
    return "По дочерним элементам"


def aggregate_sections(element) -> List[StatSection]:
    """Секции сводки для контейнерного элемента (не для отдельного упражнения)."""
    if isinstance(element, Exercise):
        return []

    exercises = _all_exercises(element)
    if not exercises:
        return [StatSection("Сводка", [("Упражнений", "0")])]

    sections: List[StatSection] = []
    total = _summarize(exercises)

    total_rows: List[Tuple[str, str]] = [("Упражнений", str(total.count))]
    if total.minutes:
        total_rows.append(("Суммарное время", _fmt_duration(total.minutes)))
    if total.km:
        total_rows.append(("Суммарный объём", f"{_fmt_num(total.km)} км"))
    sections.append(StatSection("Итого", total_rows))

    children = get_children(element)
    if children:
        child_rows: List[Tuple[str, str]] = []
        for child in children:
            child_load = _summarize(_all_exercises(child))
            child_rows.append((child.title, _fmt_load(child_load)))
        sections.append(StatSection(_child_section_title(element), child_rows))

    modality = _group_by_modality(exercises)
    if modality:
        mod_rows = [
            (name, _fmt_load(load))
            for name, load in sorted(
                modality.items(),
                key=lambda kv: (-kv[1].minutes, -kv[1].km, kv[0]),
            )
            if load.minutes or load.km or load.count
        ]
        if mod_rows:
            sections.append(StatSection("По видам нагрузки", mod_rows))

    by_type = _group_by_type(exercises)
    if by_type:
        type_rows = [
            (t.value, _fmt_load(load))
            for t, load in sorted(
                by_type.items(),
                key=lambda kv: (-kv[1].minutes, kv[0].value),
            )
            if load.minutes or load.km or load.count
        ]
        if type_rows:
            sections.append(StatSection("По типам упражнений", type_rows))

    return sections


def aggregate_stats(element) -> List[Tuple[str, str]]:
    """Плоский список пар (подпись, значение) — для обратной совместимости."""
    rows: List[Tuple[str, str]] = []
    for section in aggregate_sections(element):
        if len(aggregate_sections(element)) > 1:
            rows.append((f"— {section.title}", ""))
        rows.extend(section.rows)
    return rows
