"""Модель данных конструктора тренировочного плана.

Иерархия из 6 уровней:
    Упражнение -> Тренировка -> Микроцикл -> Мезоцикл -> Макроцикл -> Годичный план

Каждый элемент хранит собственную геометрию (pos_x, pos_y) и исходящие связи
(стрелки). Благодаря этому позиции и связи сохраняются вместе с элементом — как
в составе плана, так и при сохранении элемента в библиотеку как шаблона.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Type
import uuid


def new_id() -> str:
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────────────
# Перечисления
# ──────────────────────────────────────────────────────────────────────────

class HierarchyLevel(Enum):
    EXERCISE = 1
    WORKOUT = 2
    MICROCYCLE = 3
    MESOCYCLE = 4
    MACROCYCLE = 5
    ANNUAL = 6


# Множественное имя уровня (что мы видим на полотне)
LEVEL_NAMES: Dict[HierarchyLevel, str] = {
    HierarchyLevel.EXERCISE: "Упражнения",
    HierarchyLevel.WORKOUT: "Тренировки",
    HierarchyLevel.MICROCYCLE: "Микроциклы",
    HierarchyLevel.MESOCYCLE: "Мезоциклы",
    HierarchyLevel.MACROCYCLE: "Макроциклы",
    HierarchyLevel.ANNUAL: "Годичный план",
}

# Имя одного элемента уровня (в единственном числе)
LEVEL_ITEM_NAMES: Dict[HierarchyLevel, str] = {
    HierarchyLevel.EXERCISE: "упражнение",
    HierarchyLevel.WORKOUT: "тренировка",
    HierarchyLevel.MICROCYCLE: "микроцикл",
    HierarchyLevel.MESOCYCLE: "мезоцикл",
    HierarchyLevel.MACROCYCLE: "макроцикл",
    HierarchyLevel.ANNUAL: "годичный план",
}


class ExerciseType(Enum):
    STRENGTH = "Силовое"
    ENDURANCE = "Выносливость"
    TEMPO = "Темповое"
    SPEED = "Скоростное"
    TECHNICAL = "Техническое"
    RECOVERY = "Восстановительное"


class CycleType(Enum):
    INTRO = "Втягивающий"
    BASE = "Базовый"
    CONTROL = "Контрольно-подготовительный"
    COMPETITION = "Соревновательный"
    RECOVERY = "Восстановительный"


# Цвета плиток по типу упражнения (палитра проекта)
EXERCISE_TYPE_COLORS: Dict[ExerciseType, str] = {
    ExerciseType.STRENGTH: "#c6515c",
    ExerciseType.ENDURANCE: "#524f9d",
    ExerciseType.TEMPO: "#8a5286",
    ExerciseType.SPEED: "#600095",
    ExerciseType.TECHNICAL: "#1e2786",
    ExerciseType.RECOVERY: "#400072",
}

# Цвета плиток по типу цикла
CYCLE_TYPE_COLORS: Dict[CycleType, str] = {
    CycleType.INTRO: "#524f9d",
    CycleType.BASE: "#1e2786",
    CycleType.CONTROL: "#8a5286",
    CycleType.COMPETITION: "#c6515c",
    CycleType.RECOVERY: "#400072",
}


# ──────────────────────────────────────────────────────────────────────────
# Связь (стрелка)
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Connection:
    target_id: str
    kind: str = "sequence"  # sequence | parallel

    def to_dict(self) -> dict:
        return {"target_id": self.target_id, "kind": self.kind}

    @classmethod
    def from_dict(cls, d: dict) -> "Connection":
        return cls(target_id=d["target_id"], kind=d.get("kind", "sequence"))


# ──────────────────────────────────────────────────────────────────────────
# Элементы
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Exercise:
    id: str = field(default_factory=new_id)
    title: str = "Упражнение"
    pos_x: float = 0.0
    pos_y: float = 0.0
    notes: str = ""
    connections: List[Connection] = field(default_factory=list)

    exercise_type: ExerciseType = ExerciseType.ENDURANCE
    duration_minutes: int = 0
    volume_km: float = 0.0
    intensity_percent: int = 0
    hr_zone: str = ""
    weight_kg: float = 0.0
    sets: int = 0
    reps: int = 0
    rest_seconds: int = 0
    equipment: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "notes": self.notes,
            "connections": [c.to_dict() for c in self.connections],
            "exercise_type": self.exercise_type.value,
            "duration_minutes": self.duration_minutes,
            "volume_km": self.volume_km,
            "intensity_percent": self.intensity_percent,
            "hr_zone": self.hr_zone,
            "weight_kg": self.weight_kg,
            "sets": self.sets,
            "reps": self.reps,
            "rest_seconds": self.rest_seconds,
            "equipment": self.equipment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Exercise":
        return cls(
            id=d.get("id", new_id()),
            title=d.get("title", "Упражнение"),
            pos_x=d.get("pos_x", 0.0),
            pos_y=d.get("pos_y", 0.0),
            notes=d.get("notes", ""),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
            exercise_type=_enum_from_value(ExerciseType, d.get("exercise_type"),
                                           ExerciseType.ENDURANCE),
            duration_minutes=d.get("duration_minutes", 0),
            volume_km=d.get("volume_km", 0.0),
            intensity_percent=d.get("intensity_percent", 0),
            hr_zone=d.get("hr_zone", ""),
            weight_kg=d.get("weight_kg", 0.0),
            sets=d.get("sets", 0),
            reps=d.get("reps", 0),
            rest_seconds=d.get("rest_seconds", 0),
            equipment=d.get("equipment", ""),
        )

    def subtitle(self) -> str:
        parts: List[str] = []
        if self.duration_minutes:
            parts.append(f"{self.duration_minutes} мин")
        if self.volume_km:
            parts.append(f"{_fmt_num(self.volume_km)} км")
        if self.weight_kg:
            parts.append(f"{_fmt_num(self.weight_kg)} кг")
        if self.sets and self.reps:
            parts.append(f"{self.sets}×{self.reps}")
        if not parts:
            parts.append(self.exercise_type.value)
        return " · ".join(parts)


@dataclass
class Workout:
    id: str = field(default_factory=new_id)
    title: str = "Тренировка"
    pos_x: float = 0.0
    pos_y: float = 0.0
    notes: str = ""
    connections: List[Connection] = field(default_factory=list)

    workout_type: ExerciseType = ExerciseType.ENDURANCE
    duration_minutes: int = 0
    exercises: List[Exercise] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "notes": self.notes,
            "connections": [c.to_dict() for c in self.connections],
            "workout_type": self.workout_type.value,
            "duration_minutes": self.duration_minutes,
            "exercises": [e.to_dict() for e in self.exercises],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Workout":
        return cls(
            id=d.get("id", new_id()),
            title=d.get("title", "Тренировка"),
            pos_x=d.get("pos_x", 0.0),
            pos_y=d.get("pos_y", 0.0),
            notes=d.get("notes", ""),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
            workout_type=_enum_from_value(ExerciseType, d.get("workout_type"),
                                          ExerciseType.ENDURANCE),
            duration_minutes=d.get("duration_minutes", 0),
            exercises=[Exercise.from_dict(e) for e in d.get("exercises", [])],
        )

    def subtitle(self) -> str:
        return f"{len(self.exercises)} упр. · {self.workout_type.value}"


@dataclass
class Microcycle:
    id: str = field(default_factory=new_id)
    title: str = "Микроцикл"
    pos_x: float = 0.0
    pos_y: float = 0.0
    notes: str = ""
    connections: List[Connection] = field(default_factory=list)

    cycle_type: CycleType = CycleType.BASE
    duration_days: int = 7
    workouts: List[Workout] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "notes": self.notes,
            "connections": [c.to_dict() for c in self.connections],
            "cycle_type": self.cycle_type.value,
            "duration_days": self.duration_days,
            "workouts": [w.to_dict() for w in self.workouts],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Microcycle":
        return cls(
            id=d.get("id", new_id()),
            title=d.get("title", "Микроцикл"),
            pos_x=d.get("pos_x", 0.0),
            pos_y=d.get("pos_y", 0.0),
            notes=d.get("notes", ""),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
            cycle_type=_enum_from_value(CycleType, d.get("cycle_type"), CycleType.BASE),
            duration_days=d.get("duration_days", 7),
            workouts=[Workout.from_dict(w) for w in d.get("workouts", [])],
        )

    def subtitle(self) -> str:
        return f"{len(self.workouts)} трен. · {self.duration_days} дн."


@dataclass
class Mesocycle:
    id: str = field(default_factory=new_id)
    title: str = "Мезоцикл"
    pos_x: float = 0.0
    pos_y: float = 0.0
    notes: str = ""
    connections: List[Connection] = field(default_factory=list)

    cycle_type: CycleType = CycleType.BASE
    duration_weeks: int = 4
    microcycles: List[Microcycle] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "notes": self.notes,
            "connections": [c.to_dict() for c in self.connections],
            "cycle_type": self.cycle_type.value,
            "duration_weeks": self.duration_weeks,
            "microcycles": [m.to_dict() for m in self.microcycles],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Mesocycle":
        return cls(
            id=d.get("id", new_id()),
            title=d.get("title", "Мезоцикл"),
            pos_x=d.get("pos_x", 0.0),
            pos_y=d.get("pos_y", 0.0),
            notes=d.get("notes", ""),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
            cycle_type=_enum_from_value(CycleType, d.get("cycle_type"), CycleType.BASE),
            duration_weeks=d.get("duration_weeks", 4),
            microcycles=[Microcycle.from_dict(m) for m in d.get("microcycles", [])],
        )

    def subtitle(self) -> str:
        return f"{len(self.microcycles)} мкц · {self.duration_weeks} нед."


@dataclass
class Macrocycle:
    id: str = field(default_factory=new_id)
    title: str = "Макроцикл"
    pos_x: float = 0.0
    pos_y: float = 0.0
    notes: str = ""
    connections: List[Connection] = field(default_factory=list)

    duration_months: int = 3
    mesocycles: List[Mesocycle] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "notes": self.notes,
            "connections": [c.to_dict() for c in self.connections],
            "duration_months": self.duration_months,
            "mesocycles": [m.to_dict() for m in self.mesocycles],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Macrocycle":
        return cls(
            id=d.get("id", new_id()),
            title=d.get("title", "Макроцикл"),
            pos_x=d.get("pos_x", 0.0),
            pos_y=d.get("pos_y", 0.0),
            notes=d.get("notes", ""),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
            duration_months=d.get("duration_months", 3),
            mesocycles=[Mesocycle.from_dict(m) for m in d.get("mesocycles", [])],
        )

    def subtitle(self) -> str:
        return f"{len(self.mesocycles)} мзц · {self.duration_months} мес."


@dataclass
class AnnualPlan:
    id: str = field(default_factory=new_id)
    title: str = "Годичный план"
    pos_x: float = 0.0
    pos_y: float = 0.0
    notes: str = ""
    connections: List[Connection] = field(default_factory=list)

    year: int = 2026
    sport_type: str = ""
    macrocycles: List[Macrocycle] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "notes": self.notes,
            "connections": [c.to_dict() for c in self.connections],
            "year": self.year,
            "sport_type": self.sport_type,
            "macrocycles": [m.to_dict() for m in self.macrocycles],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnnualPlan":
        return cls(
            id=d.get("id", new_id()),
            title=d.get("title", "Годичный план"),
            pos_x=d.get("pos_x", 0.0),
            pos_y=d.get("pos_y", 0.0),
            notes=d.get("notes", ""),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
            year=d.get("year", 2026),
            sport_type=d.get("sport_type", ""),
            macrocycles=[Macrocycle.from_dict(m) for m in d.get("macrocycles", [])],
        )

    def subtitle(self) -> str:
        return f"{len(self.macrocycles)} макроциклов · {self.year}"


# Любой элемент плана
PlanElement = (Exercise, Workout, Microcycle, Mesocycle, Macrocycle, AnnualPlan)


# ──────────────────────────────────────────────────────────────────────────
# Таблицы соответствий типов и уровней
# ──────────────────────────────────────────────────────────────────────────

_TYPE_BY_LEVEL: Dict[HierarchyLevel, Type] = {
    HierarchyLevel.EXERCISE: Exercise,
    HierarchyLevel.WORKOUT: Workout,
    HierarchyLevel.MICROCYCLE: Microcycle,
    HierarchyLevel.MESOCYCLE: Mesocycle,
    HierarchyLevel.MACROCYCLE: Macrocycle,
    HierarchyLevel.ANNUAL: AnnualPlan,
}

_LEVEL_BY_TYPE: Dict[Type, HierarchyLevel] = {v: k for k, v in _TYPE_BY_LEVEL.items()}

# Имя атрибута со списком детей
_CHILD_ATTR: Dict[Type, str] = {
    Workout: "exercises",
    Microcycle: "workouts",
    Mesocycle: "microcycles",
    Macrocycle: "mesocycles",
    AnnualPlan: "macrocycles",
}

# Тип ключа сериализации для library_store
TYPE_KEYS: Dict[Type, str] = {
    Exercise: "exercise",
    Workout: "workout",
    Microcycle: "microcycle",
    Mesocycle: "mesocycle",
    Macrocycle: "macrocycle",
    AnnualPlan: "annual",
}
TYPE_BY_KEY: Dict[str, Type] = {v: k for k, v in TYPE_KEYS.items()}


def level_of(element) -> HierarchyLevel:
    return _LEVEL_BY_TYPE[type(element)]


def child_level(level: HierarchyLevel) -> Optional[HierarchyLevel]:
    if level.value <= 1:
        return None
    return HierarchyLevel(level.value - 1)


def child_attr(element) -> Optional[str]:
    return _CHILD_ATTR.get(type(element))


def get_children(element) -> List:
    attr = child_attr(element)
    return getattr(element, attr) if attr else []


def make_element(level: HierarchyLevel, title: Optional[str] = None):
    """Создаёт пустой элемент заданного уровня."""
    cls = _TYPE_BY_LEVEL[level]
    el = cls()
    if title:
        el.title = title
    return el


def regenerate_ids(element) -> None:
    """Назначает новые id элементу и всем потомкам, переотображая связи детей.

    Собственные (исходящие) связи верхнего элемента очищаются: после смены id
    соседей они становятся недействительными.
    """
    element.id = new_id()
    element.connections = []
    _remap_children_ids(element)


def _remap_children_ids(element) -> None:
    id_map: Dict[str, str] = {}
    children = get_children(element)
    for child in children:
        old = child.id
        child.id = new_id()
        id_map[old] = child.id
    for child in children:
        for conn in getattr(child, "connections", []):
            conn.target_id = id_map.get(conn.target_id, conn.target_id)
        _remap_children_ids(child)


def clone_element(element):
    """Возвращает независимую копию элемента с новыми идентификаторами."""
    copy = type(element).from_dict(element.to_dict())
    regenerate_ids(copy)
    return copy


def element_color(element) -> str:
    if isinstance(element, Exercise):
        return EXERCISE_TYPE_COLORS.get(element.exercise_type, "#5a6acf")
    if isinstance(element, (Microcycle, Mesocycle)):
        return CYCLE_TYPE_COLORS.get(element.cycle_type, "#5a6acf")
    if isinstance(element, Workout):
        return EXERCISE_TYPE_COLORS.get(element.workout_type, "#5a6acf")
    if isinstance(element, Macrocycle):
        return "#600095"
    if isinstance(element, AnnualPlan):
        return "#1e2786"
    return "#524f9d"


def element_type_key(element) -> str:
    return TYPE_KEYS.get(type(element), "exercise")


# ──────────────────────────────────────────────────────────────────────────
# Иерархия плана
# ──────────────────────────────────────────────────────────────────────────

class TrainingPlan:
    """Контейнер всего плана с индексами id->элемент и id->родитель."""

    def __init__(self, annual: Optional[AnnualPlan] = None):
        self.annual: AnnualPlan = annual or AnnualPlan()
        self._by_id: Dict[str, object] = {}
        self._parent: Dict[str, Optional[str]] = {}
        self.reindex()

    # — индексация —
    def reindex(self) -> None:
        self._by_id.clear()
        self._parent.clear()

        def walk(element, parent_id: Optional[str]):
            self._by_id[element.id] = element
            self._parent[element.id] = parent_id
            for child in get_children(element):
                walk(child, element.id)

        walk(self.annual, None)

    # — доступ —
    def get(self, element_id: Optional[str]):
        if element_id is None:
            return None
        return self._by_id.get(element_id)

    def parent_id(self, element_id: str) -> Optional[str]:
        return self._parent.get(element_id)

    def parent_of(self, element_id: str):
        return self.get(self.parent_id(element_id))

    def children_of(self, element_id: Optional[str]) -> List:
        element = self.get(element_id)
        if element is None:
            return []
        return get_children(element)

    # — изменение —
    def add_child(self, parent_id: Optional[str], element) -> bool:
        parent = self.get(parent_id) if parent_id else self.annual
        if parent is None:
            return False
        attr = child_attr(parent)
        if not attr:
            return False
        getattr(parent, attr).append(element)
        self._by_id[element.id] = element
        self._parent[element.id] = parent.id

        def index_children(el):
            for child in get_children(el):
                self._by_id[child.id] = child
                self._parent[child.id] = el.id
                index_children(child)

        index_children(element)
        return True

    def remove(self, element_id: str) -> bool:
        element = self.get(element_id)
        if element is None or element is self.annual:
            return False
        parent = self.parent_of(element_id)
        if parent is not None:
            attr = child_attr(parent)
            if attr:
                lst = getattr(parent, attr)
                if element in lst:
                    lst.remove(element)
            # удалить связи, ведущие к удаляемому элементу
            for sibling in getattr(parent, attr, []):
                sibling.connections = [
                    c for c in sibling.connections if c.target_id != element_id
                ]

        def drop(el):
            self._by_id.pop(el.id, None)
            self._parent.pop(el.id, None)
            for child in get_children(el):
                drop(child)

        drop(element)
        return True

    # — связи —
    def add_connection(self, source_id: str, target_id: str,
                       kind: str = "sequence") -> bool:
        source = self.get(source_id)
        target = self.get(target_id)
        if source is None or target is None or source_id == target_id:
            return False
        if self.parent_id(source_id) != self.parent_id(target_id):
            return False  # связи только между соседями одного контейнера
        for c in source.connections:
            if c.target_id == target_id:
                return False  # связь уже есть
        source.connections.append(Connection(target_id=target_id, kind=kind))
        return True

    def remove_connection(self, source_id: str, target_id: str) -> None:
        source = self.get(source_id)
        if source is None:
            return
        source.connections = [
            c for c in source.connections if c.target_id != target_id
        ]

    # — сериализация —
    def to_dict(self) -> dict:
        return {"version": 1, "annual": self.annual.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingPlan":
        annual = AnnualPlan.from_dict(d.get("annual", {}))
        return cls(annual=annual)


# ──────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────

def _enum_from_value(enum_cls, value, default):
    if value is None:
        return default
    for item in enum_cls:
        if item.value == value or item.name == value:
            return item
    return default


def _fmt_num(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
