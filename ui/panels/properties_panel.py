"""Правая панель: параметры выбранного элемента (поля зависят от типа)."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from core.models import (
    AnnualPlan, CycleType, Exercise, ExerciseType, Macrocycle, Mesocycle,
    Microcycle, Workout,
)

# Типы упражнений, для которых показываем объём/интенсивность
_VOLUME_TYPES = {
    ExerciseType.ENDURANCE, ExerciseType.TEMPO,
    ExerciseType.SPEED, ExerciseType.TECHNICAL,
}


class PropertiesPanel(QFrame):
    data_changed = pyqtSignal(object)
    save_to_library = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("properties_panel")
        self.element = None
        self._loading = False
        self._w: dict = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.title_label = QLabel("Свойства")
        self.title_label.setObjectName("panel_title")
        root.addWidget(self.title_label)

        self.hint = QLabel("Выберите элемент на полотне")
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.form_host = QWidget()
        self.form_layout = QVBoxLayout(self.form_host)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(10)
        self.form_layout.addStretch()
        self.scroll.setWidget(self.form_host)
        root.addWidget(self.scroll, 1)

        self.btn_library = QPushButton("★  Сохранить как шаблон")
        self.btn_library.setObjectName("accent")
        self.btn_library.clicked.connect(self._on_save_to_library)
        self.btn_library.setVisible(False)
        root.addWidget(self.btn_library)

    # ──────────────────────────────────────────────────────────────────
    def show_placeholder(self) -> None:
        self.element = None
        self._clear_form()
        self.title_label.setText("Свойства")
        self.hint.setVisible(True)
        self.btn_library.setVisible(False)

    def set_element(self, element) -> None:
        self.element = element
        if element is None:
            self.show_placeholder()
            return
        self.hint.setVisible(False)
        self.btn_library.setVisible(True)
        self._rebuild()

    # ──────────────────────────────────────────────────────────────────
    def _clear_form(self) -> None:
        self._w.clear()
        while self.form_layout.count() > 1:
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild(self) -> None:
        self._loading = True
        self._clear_form()
        el = self.element
        if isinstance(el, Exercise):
            self._build_exercise(el)
        elif isinstance(el, Workout):
            self._build_workout(el)
        elif isinstance(el, Microcycle):
            self._build_microcycle(el)
        elif isinstance(el, Mesocycle):
            self._build_mesocycle(el)
        elif isinstance(el, Macrocycle):
            self._build_macrocycle(el)
        elif isinstance(el, AnnualPlan):
            self._build_annual(el)
        self._build_aggregates(el)  # опциональная сводка (см. core/aggregates.py)
        self._loading = False

    def _build_aggregates(self, el) -> None:
        """Read-only сводка по вложенным элементам. Полностью необязательна:
        чтобы убрать — удалить этот метод, его вызов и core/aggregates.py."""
        try:
            from core.aggregates import aggregate_sections
        except ImportError:
            return
        sections = aggregate_sections(el)
        if not sections:
            return
        for section in sections:
            lay = self._group(f"Сводка — {section.title}")
            for label, value in section.rows:
                field = QLineEdit(value)
                field.setReadOnly(True)
                lay.addRow(label + ":", field)

    # ── строители форм ──
    def _group(self, title: str) -> QFormLayout:
        box = QFrame()
        box.setObjectName("group")
        lay = QFormLayout(box)
        lay.setContentsMargins(12, 14, 12, 12)
        lay.setSpacing(9)
        lay.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        header = QLabel(title)
        header.setObjectName("group_title")
        self.form_layout.insertWidget(self.form_layout.count() - 1, header)
        self.form_layout.insertWidget(self.form_layout.count() - 1, box)
        return lay

    def _build_exercise(self, ex: Exercise) -> None:
        self.title_label.setText("Упражнение")
        lay = self._group("Основное")
        self._w["title"] = self._line(lay, "Название", ex.title)
        self._w["type"] = self._combo(lay, "Тип", [t.value for t in ExerciseType],
                                      ex.exercise_type.value, on_change=self._on_type_changed)
        self._w["duration"] = self._spin(lay, "Длительность", ex.duration_minutes, 0, 1000, " мин")

        is_recovery = ex.exercise_type == ExerciseType.RECOVERY
        is_strength = ex.exercise_type == ExerciseType.STRENGTH

        if is_strength:
            lay2 = self._group("Силовые параметры")
            self._w["weight"] = self._dspin(lay2, "Рабочий вес", ex.weight_kg, 0, 1000, " кг")
            self._w["sets"] = self._spin(lay2, "Подходы", ex.sets, 0, 100, "")
            self._w["reps"] = self._spin(lay2, "Повторения", ex.reps, 0, 1000, "")
            self._w["rest"] = self._spin(lay2, "Отдых", ex.rest_seconds, 0, 3600, " сек")
            self._w["equipment"] = self._line(lay2, "Инвентарь", ex.equipment)
        elif is_recovery:
            lay2 = self._group("Восстановление")
            self._w["equipment"] = self._line(lay2, "Инвентарь", ex.equipment)
        else:
            lay2 = self._group("Объём и интенсивность")
            self._w["volume"] = self._dspin(lay2, "Объём", ex.volume_km, 0, 1000, " км")
            self._w["intensity"] = self._spin(lay2, "Интенсивность", ex.intensity_percent, 0, 100, " %")
            self._w["hr_zone"] = self._line(lay2, "Зона ЧСС", ex.hr_zone)
            self._w["sets"] = self._spin(lay2, "Серии", ex.sets, 0, 100, "")
            self._w["reps"] = self._spin(lay2, "Повторы", ex.reps, 0, 1000, "")
            self._w["rest"] = self._spin(lay2, "Отдых", ex.rest_seconds, 0, 3600, " сек")
            self._w["equipment"] = self._line(lay2, "Инвентарь", ex.equipment)

        lay3 = self._group("Заметки")
        self._w["notes"] = self._text(lay3, ex.notes)

    def _build_workout(self, w: Workout) -> None:
        self.title_label.setText("Тренировка")
        lay = self._group("Основное")
        self._w["title"] = self._line(lay, "Название", w.title)
        self._w["type"] = self._combo(lay, "Направленность",
                                      [t.value for t in ExerciseType], w.workout_type.value)
        self._w["duration"] = self._spin(lay, "Длительность", w.duration_minutes, 0, 1000, " мин")
        self._info(f"Содержит упражнений: {len(w.exercises)}")
        lay3 = self._group("Заметки")
        self._w["notes"] = self._text(lay3, w.notes)

    def _build_microcycle(self, m: Microcycle) -> None:
        self.title_label.setText("Микроцикл")
        lay = self._group("Основное")
        self._w["title"] = self._line(lay, "Название", m.title)
        self._w["cycle_type"] = self._combo(lay, "Тип", [t.value for t in CycleType],
                                            m.cycle_type.value)
        self._w["days"] = self._spin(lay, "Длительность", m.duration_days, 1, 31, " дн.")
        self._info(f"Содержит тренировок: {len(m.workouts)}")
        lay3 = self._group("Заметки")
        self._w["notes"] = self._text(lay3, m.notes)

    def _build_mesocycle(self, m: Mesocycle) -> None:
        self.title_label.setText("Мезоцикл")
        lay = self._group("Основное")
        self._w["title"] = self._line(lay, "Название", m.title)
        self._w["cycle_type"] = self._combo(lay, "Тип", [t.value for t in CycleType],
                                            m.cycle_type.value)
        self._w["weeks"] = self._spin(lay, "Длительность", m.duration_weeks, 1, 52, " нед.")
        self._info(f"Содержит микроциклов: {len(m.microcycles)}")
        lay3 = self._group("Заметки")
        self._w["notes"] = self._text(lay3, m.notes)

    def _build_macrocycle(self, m: Macrocycle) -> None:
        self.title_label.setText("Макроцикл")
        lay = self._group("Основное")
        self._w["title"] = self._line(lay, "Название", m.title)
        self._w["months"] = self._spin(lay, "Длительность", m.duration_months, 1, 24, " мес.")
        self._info(f"Содержит мезоциклов: {len(m.mesocycles)}")
        lay3 = self._group("Заметки")
        self._w["notes"] = self._text(lay3, m.notes)

    def _build_annual(self, a: AnnualPlan) -> None:
        self.title_label.setText("Годичный план")
        lay = self._group("Основное")
        self._w["title"] = self._line(lay, "Название", a.title)
        self._w["year"] = self._spin(lay, "Год", a.year, 1900, 2200, "")
        self._w["sport"] = self._line(lay, "Вид спорта", a.sport_type)
        self._info(f"Содержит макроциклов: {len(a.macrocycles)}")
        lay3 = self._group("Заметки")
        self._w["notes"] = self._text(lay3, a.notes)

    # ── фабрики виджетов ──
    def _line(self, lay: QFormLayout, label: str, value: str) -> QLineEdit:
        w = QLineEdit(value)
        w.textChanged.connect(self._commit)
        lay.addRow(label + ":", w)
        return w

    def _text(self, lay: QFormLayout, value: str) -> QTextEdit:
        w = QTextEdit(value)
        w.setMaximumHeight(90)
        w.textChanged.connect(self._commit)
        lay.addRow(w)
        return w

    def _spin(self, lay: QFormLayout, label: str, value: int,
              lo: int, hi: int, suffix: str) -> QSpinBox:
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(int(value))
        if suffix:
            w.setSuffix(suffix)
        w.valueChanged.connect(self._commit)
        lay.addRow(label + ":", w)
        return w

    def _dspin(self, lay: QFormLayout, label: str, value: float,
               lo: float, hi: float, suffix: str) -> QDoubleSpinBox:
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(1)
        w.setSingleStep(0.5)
        w.setValue(float(value))
        if suffix:
            w.setSuffix(suffix)
        w.valueChanged.connect(self._commit)
        lay.addRow(label + ":", w)
        return w

    def _combo(self, lay: QFormLayout, label: str, items: list, current: str,
               on_change=None) -> QComboBox:
        w = QComboBox()
        w.addItems(items)
        if current in items:
            w.setCurrentText(current)
        w.currentTextChanged.connect(on_change or self._commit)
        lay.addRow(label + ":", w)
        return w

    def _info(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("hint")
        self.form_layout.insertWidget(self.form_layout.count() - 1, lbl)

    # ──────────────────────────────────────────────────────────────────
    def _on_type_changed(self, _value: str) -> None:
        if self._loading or self.element is None:
            return
        self._commit()
        self._rebuild()

    def _commit(self) -> None:
        if self._loading or self.element is None:
            return
        el = self.element
        w = self._w
        if "title" in w:
            el.title = w["title"].text()
        if "notes" in w:
            el.notes = w["notes"].toPlainText()

        if isinstance(el, Exercise):
            el.exercise_type = _enum(ExerciseType, w["type"].currentText(), el.exercise_type)
            el.duration_minutes = w["duration"].value()
            el.weight_kg = w["weight"].value() if "weight" in w else 0.0
            el.volume_km = w["volume"].value() if "volume" in w else 0.0
            el.intensity_percent = w["intensity"].value() if "intensity" in w else 0
            el.hr_zone = w["hr_zone"].text() if "hr_zone" in w else ""
            el.sets = w["sets"].value() if "sets" in w else 0
            el.reps = w["reps"].value() if "reps" in w else 0
            el.rest_seconds = w["rest"].value() if "rest" in w else 0
            el.equipment = w["equipment"].text() if "equipment" in w else ""
        elif isinstance(el, Workout):
            el.workout_type = _enum(ExerciseType, w["type"].currentText(), el.workout_type)
            el.duration_minutes = w["duration"].value()
        elif isinstance(el, Microcycle):
            el.cycle_type = _enum(CycleType, w["cycle_type"].currentText(), el.cycle_type)
            el.duration_days = w["days"].value()
        elif isinstance(el, Mesocycle):
            el.cycle_type = _enum(CycleType, w["cycle_type"].currentText(), el.cycle_type)
            el.duration_weeks = w["weeks"].value()
        elif isinstance(el, Macrocycle):
            el.duration_months = w["months"].value()
        elif isinstance(el, AnnualPlan):
            el.year = w["year"].value()
            el.sport_type = w["sport"].text()

        self.data_changed.emit(el)

    def _on_save_to_library(self) -> None:
        if self.element is not None:
            self.save_to_library.emit(self.element)


def _enum(enum_cls, value, default):
    for item in enum_cls:
        if item.value == value:
            return item
    return default
