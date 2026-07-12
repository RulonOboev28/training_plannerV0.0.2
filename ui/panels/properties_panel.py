"""Правая панель: параметры выбранного элемента (поля зависят от типа)."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDoubleSpinBox, QFormLayout, QFrame, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from core.calendar_map import element_date_info, format_display, format_iso, parse_iso_date
from core.date_cascade import apply_manual_date, clear_manual_dates_in_subtree
from core.models import (
    AnnualPlan, CycleType, Exercise, ExerciseType, HierarchyLevel, Macrocycle,
    Mesocycle, Microcycle, Workout,
)

if TYPE_CHECKING:
    from ui.canvas.viewport import CanvasView

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
        self._canvas: Optional[CanvasView] = None
        self._date_override_keys: set[str] = set()

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
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.form_host = QWidget()
        self.form_host.setMinimumWidth(0)
        self.form_layout = QVBoxLayout(self.form_host)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(10)
        self.form_layout.addStretch()
        self.scroll.setWidget(self.form_host)
        root.addWidget(self.scroll, 1)

        self.btn_library = QPushButton("★  Сохранить как шаблон")
        self.btn_library.setObjectName("accent")
        self.btn_library.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_library.clicked.connect(self._on_save_to_library)
        self.btn_library.setVisible(False)
        root.addWidget(self.btn_library)

    # ──────────────────────────────────────────────────────────────────
    def bind_canvas(self, canvas: CanvasView) -> None:
        self._canvas = canvas
        canvas.level_changed.connect(self._on_canvas_context_changed)
        canvas.plan_changed.connect(self._on_canvas_context_changed)

    def _on_canvas_context_changed(self, *_args) -> None:
        if self.element is not None and not self._loading:
            self._rebuild()

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
        self._date_override_keys.clear()
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
        self._build_aggregates(el)
        self._build_dates_section(el)
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
                field = self._responsive_field(QLineEdit(value))
                field.setReadOnly(True)
                lay.addRow(label + ":", field)

    # ── строители форм ──
    def _group(self, title: str) -> QFormLayout:
        box = QFrame()
        box.setObjectName("group")
        box.setMinimumWidth(0)
        lay = QFormLayout(box)
        lay.setContentsMargins(10, 12, 10, 10)
        lay.setSpacing(8)
        lay.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        lay.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        lay.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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

    def _build_dates_section(self, el) -> None:
        if self._canvas is None:
            return
        plan = self._canvas.plan
        info = element_date_info(plan, el.id)

        if isinstance(el, Exercise):
            if not self._show_exercise_date():
                return
            lay = self._group("Дата")
            self._w["scheduled_date"] = self._date_field(
                lay, "Дата выполнения", el.scheduled_date,
                info.computed_start, key="scheduled_date")
            return

        if isinstance(el, Workout):
            lay = self._group("Дата")
            self._w["start_date"] = self._date_field(
                lay, "Дата тренировки", el.start_date,
                info.computed_start, key="start_date")
            return

        if isinstance(el, Microcycle):
            lay = self._group("Даты")
            self._w["start_date"] = self._date_field(
                lay, "Начало", el.start_date, info.computed_start, key="start_date")
            self._w["end_date"] = self._date_field(
                lay, "Окончание", el.end_date, info.computed_end, key="end_date")
            return

        if isinstance(el, (Mesocycle, Macrocycle)):
            lay = self._group("Даты")
            self._w["start_date"] = self._date_field(
                lay, "Начало", el.start_date, info.computed_start, key="start_date")
            self._w["end_date"] = self._date_field(
                lay, "Окончание", el.end_date, info.computed_end, key="end_date")
            return

        if isinstance(el, AnnualPlan):
            lay = self._group("Дата")
            anchor = info.computed_start or info.start
            stored = el.start_date or plan.plan_start_date
            self._w["start_date"] = self._date_field(
                lay, "Начало плана", stored, anchor, key="start_date")

    def _show_exercise_date(self) -> bool:
        """Дата упражнения видна на стадии микроцикла (не внутри одной тренировки)."""
        if self._canvas is None:
            return False
        return self._canvas.area_level() == HierarchyLevel.WORKOUT

    def _date_field(self, lay: QFormLayout, label: str, stored: Optional[str],
                    computed, key: str) -> QDateEdit:
        w = QDateEdit()
        w.setCalendarPopup(True)
        w.setDisplayFormat("dd.MM.yyyy")
        self._responsive_field(w)
        effective = parse_iso_date(stored) or computed
        w.blockSignals(True)
        if effective is not None:
            w.setDate(QDate(effective.year, effective.month, effective.day))
        w.blockSignals(False)
        w.dateChanged.connect(lambda: self._mark_date_override(key))
        w.dateChanged.connect(self._commit)
        lay.addRow(label + ":", w)

        hint = QLabel(self._date_hint(stored, computed))
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setMinimumWidth(0)
        lay.addRow("", hint)
        self._w[f"{key}_hint"] = hint

        if stored:
            btn = QPushButton("Сбросить → расчёт")
            btn.setFlat(True)
            btn.setObjectName("cal_toggle")
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, k=key: self._reset_date(k))
            lay.addRow("", btn)
        return w

    def _date_hint(self, stored: Optional[str], computed) -> str:
        if stored:
            return f"Задано вручную. Расчёт: {format_display(computed)}"
        if computed is not None:
            return f"Рассчитывается автоматически: {format_display(computed)}"
        return "Дата будет рассчитана по положению в плане"

    def _mark_date_override(self, key: str) -> None:
        if not self._loading:
            self._date_override_keys.add(key)

    def _reset_date(self, key: str) -> None:
        if self.element is None or self._canvas is None:
            return
        el = self.element
        plan = self._canvas.plan
        if key == "scheduled_date" and isinstance(el, Exercise):
            el.scheduled_date = None
        elif key == "start_date":
            el.start_date = None
            if isinstance(el, AnnualPlan):
                plan.plan_start_date = None
            if isinstance(el, (Microcycle, Mesocycle, Macrocycle)):
                clear_manual_dates_in_subtree(el)
        elif key == "end_date":
            el.end_date = None
        self._date_override_keys.discard(key)
        self.data_changed.emit(el)
        self._rebuild()

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
    def _responsive_field(self, w: QWidget) -> QWidget:
        """Поля растягиваются на ширину панели и не обрезаются при сужении."""
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        w.setMinimumWidth(0)
        return w

    def _line(self, lay: QFormLayout, label: str, value: str) -> QLineEdit:
        w = self._responsive_field(QLineEdit(value))
        w.textChanged.connect(self._commit)
        lay.addRow(label + ":", w)
        return w

    def _text(self, lay: QFormLayout, value: str) -> QTextEdit:
        w = QTextEdit(value)
        w.setMaximumHeight(90)
        w.setMinimumWidth(0)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        w.textChanged.connect(self._commit)
        lay.addRow(w)
        return w

    def _spin(self, lay: QFormLayout, label: str, value: int,
              lo: int, hi: int, suffix: str) -> QSpinBox:
        w = self._responsive_field(QSpinBox())
        w.setRange(lo, hi)
        w.setValue(int(value))
        if suffix:
            w.setSuffix(suffix)
        w.valueChanged.connect(self._commit)
        lay.addRow(label + ":", w)
        return w

    def _dspin(self, lay: QFormLayout, label: str, value: float,
               lo: float, hi: float, suffix: str) -> QDoubleSpinBox:
        w = self._responsive_field(QDoubleSpinBox())
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
        w = self._responsive_field(QComboBox())
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

        self._commit_dates(el)
        self.data_changed.emit(el)

    def _commit_dates(self, el) -> None:
        if not self._date_override_keys or self._canvas is None:
            return

        plan = self._canvas.plan
        for key in list(self._date_override_keys):
            widget = self._w.get(key)
            if widget is None:
                continue
            new_date = widget.date().toPyDate()
            apply_manual_date(plan, el.id, key, new_date)

        self._date_override_keys.clear()
        self._rebuild()

    def _on_save_to_library(self) -> None:
        if self.element is not None:
            self.save_to_library.emit(self.element)


def _enum(enum_cls, value, default):
    for item in enum_cls:
        if item.value == value:
            return item
    return default
