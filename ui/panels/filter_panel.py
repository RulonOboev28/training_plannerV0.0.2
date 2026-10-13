"""Правая панель фильтра при множественном выборе плиток."""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout,
)

from core.models import CycleType, Exercise, ExerciseType, Microcycle, Mesocycle, Workout

if TYPE_CHECKING:
    from ui.canvas.viewport import CanvasView

_PARAM_EXERCISE = [
    ("title", "Название", "text"),
    ("volume_km", "Объём (км)", "float"),
    ("intensity_percent", "Интенсивность (%)", "int"),
    ("duration_minutes", "Длительность (мин)", "int"),
    ("hr_zone", "Зона ЧСС", "text"),
]

_PARAM_WORKOUT = [
    ("title", "Название", "text"),
    ("duration_minutes", "Длительность (мин)", "int"),
]


class FilterPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("properties_panel")
        self._canvas: Optional[CanvasView] = None
        self._elements: List = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.title_label = QLabel("Фильтр выделения")
        self.title_label.setObjectName("panel_title")
        root.addWidget(self.title_label)

        self.count_label = QLabel("")
        self.count_label.setObjectName("hint")
        self.count_label.setWordWrap(True)
        root.addWidget(self.count_label)

        form = QFormLayout()
        form.setSpacing(8)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Любой тип", None)
        form.addRow("Тип:", self.type_combo)

        self.param_combo = QComboBox()
        form.addRow("Параметр:", self.param_combo)

        self.value_text = QLineEdit()
        self.value_text.setPlaceholderText("Значение или часть названия")
        form.addRow("Значение:", self.value_text)

        self.value_int = QSpinBox()
        self.value_int.setRange(0, 100000)
        self.value_int.setVisible(False)
        form.addRow("", self.value_int)

        self.value_float = QDoubleSpinBox()
        self.value_float.setRange(0.0, 100000.0)
        self.value_float.setDecimals(2)
        self.value_float.setVisible(False)
        form.addRow("", self.value_float)

        root.addLayout(form)

        self.btn_apply = QPushButton("Оставить подходящие")
        self.btn_apply.setObjectName("accent")
        self.btn_apply.clicked.connect(self._apply_filter)
        root.addWidget(self.btn_apply)

        self.btn_reset = QPushButton("Сбросить фильтр")
        self.btn_reset.clicked.connect(self._reset_selection)
        root.addWidget(self.btn_reset)

        self.result_label = QLabel("")
        self.result_label.setObjectName("hint")
        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)
        root.addStretch()

        self.param_combo.currentIndexChanged.connect(self._on_param_changed)

    def bind_canvas(self, canvas: CanvasView) -> None:
        self._canvas = canvas

    def set_selection(self, elements: List) -> None:
        self._elements = list(elements)
        self.count_label.setText(f"Выбрано элементов: {len(elements)}")
        self._rebuild_type_combo()
        self._rebuild_param_combo()
        self.result_label.clear()

    def _rebuild_type_combo(self) -> None:
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        self.type_combo.addItem("Любой тип", None)
        sample = self._elements[0] if self._elements else None
        if isinstance(sample, Exercise):
            for t in ExerciseType:
                self.type_combo.addItem(t.value, t)
        elif isinstance(sample, Workout):
            for t in ExerciseType:
                self.type_combo.addItem(t.value, t)
        elif isinstance(sample, (Microcycle, Mesocycle)):
            for t in CycleType:
                self.type_combo.addItem(t.value, t)
        self.type_combo.blockSignals(False)

    def _rebuild_param_combo(self) -> None:
        self.param_combo.blockSignals(True)
        self.param_combo.clear()
        sample = self._elements[0] if self._elements else None
        params = _PARAM_EXERCISE if isinstance(sample, Exercise) else (
            _PARAM_WORKOUT if isinstance(sample, Workout) else [])
        for key, label, _kind in params:
            self.param_combo.addItem(label, (key, _kind))
        self.param_combo.blockSignals(False)
        self._on_param_changed()

    def _on_param_changed(self) -> None:
        data = self.param_combo.currentData()
        kind = data[1] if data else "text"
        self.value_text.setVisible(kind == "text")
        self.value_int.setVisible(kind == "int")
        self.value_float.setVisible(kind == "float")

    def _apply_filter(self) -> None:
        if not self._elements or self._canvas is None:
            return
        matched = [el for el in self._elements if self._matches(el)]
        self._canvas.select_elements(matched)
        self.result_label.setText(
            f"Оставлено в выделении: {len(matched)} из {len(self._elements)}")

    def _reset_selection(self) -> None:
        if self._canvas is not None and self._elements:
            self._canvas.select_elements(self._elements)
            self.result_label.setText(f"Выделено: {len(self._elements)}")

    def _matches(self, el) -> bool:
        type_filter = self.type_combo.currentData()
        if isinstance(el, Exercise) and type_filter is not None:
            if el.exercise_type != type_filter:
                return False
        if isinstance(el, Workout) and type_filter is not None:
            if el.workout_type != type_filter:
                return False
        if isinstance(el, (Microcycle, Mesocycle)) and type_filter is not None:
            if el.cycle_type != type_filter:
                return False

        data = self.param_combo.currentData()
        if not data:
            return True
        key, kind = data
        if kind == "text":
            needle = self.value_text.text().strip().lower()
            if not needle:
                return True
            hay = str(getattr(el, key, "") or "").lower()
            return needle in hay
        if kind == "int":
            return int(getattr(el, key, 0) or 0) == self.value_int.value()
        if kind == "float":
            return abs(float(getattr(el, key, 0) or 0) - self.value_float.value()) < 1e-6
        return True
