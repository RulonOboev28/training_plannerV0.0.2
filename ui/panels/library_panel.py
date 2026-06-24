"""Левая панель: библиотека компонентов для текущего уровня."""
from __future__ import annotations

import json
from typing import Dict, List

from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QColor, QDrag, QFont
from PyQt6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QTabWidget, QVBoxLayout,
)

from core import library_store
from core.models import (
    CycleType, Exercise, ExerciseType, HierarchyLevel, LEVEL_ITEM_NAMES,
    LEVEL_NAMES, element_type_key, level_of, make_element,
)


def _entry_from_element(el) -> Dict:
    return {
        "title": el.title,
        "type": element_type_key(el),
        "level": level_of(el).value,
        "payload": el.to_dict(),
    }


def _exercise(title: str, etype: ExerciseType, **kw) -> Exercise:
    ex = Exercise(title=title, exercise_type=etype)
    for k, v in kw.items():
        setattr(ex, k, v)
    return ex


def _preset_entries(level: HierarchyLevel) -> List[Dict]:
    """Базовые пресеты по уровням."""
    if level == HierarchyLevel.EXERCISE:
        items = [
            _exercise("Лёгкий кросс", ExerciseType.ENDURANCE, duration_minutes=40,
                      volume_km=8, intensity_percent=65, hr_zone="Z2"),
            _exercise("Темповой бег", ExerciseType.TEMPO, duration_minutes=30,
                      volume_km=6, intensity_percent=85, hr_zone="Z3-Z4"),
            _exercise("Интервалы", ExerciseType.SPEED, duration_minutes=25,
                      intensity_percent=92, sets=6, reps=1, rest_seconds=120),
            _exercise("Присед со штангой", ExerciseType.STRENGTH, weight_kg=80,
                      sets=4, reps=8, rest_seconds=120),
            _exercise("Растяжка", ExerciseType.RECOVERY, duration_minutes=15),
        ]
    elif level == HierarchyLevel.WORKOUT:
        items = [
            make_element(level, "Утренняя пробежка"),
            make_element(level, "Силовая тренировка"),
            make_element(level, "Интервальная"),
            make_element(level, "Восстановительная"),
        ]
        items[1].workout_type = ExerciseType.STRENGTH
        items[3].workout_type = ExerciseType.RECOVERY
    elif level == HierarchyLevel.MICROCYCLE:
        items = []
        for title, ct in [("Втягивающая неделя", CycleType.INTRO),
                          ("Базовая неделя", CycleType.BASE),
                          ("Ударная неделя", CycleType.CONTROL),
                          ("Восстановительная неделя", CycleType.RECOVERY)]:
            el = make_element(level, title)
            el.cycle_type = ct
            items.append(el)
    elif level == HierarchyLevel.MESOCYCLE:
        items = []
        for title, ct in [("Подготовительный", CycleType.BASE),
                          ("Предсоревновательный", CycleType.CONTROL),
                          ("Соревновательный", CycleType.COMPETITION)]:
            el = make_element(level, title)
            el.cycle_type = ct
            items.append(el)
    elif level == HierarchyLevel.MACROCYCLE:
        items = [make_element(level, "Подготовительный этап"),
                 make_element(level, "Соревновательный этап"),
                 make_element(level, "Переходный этап")]
    else:
        items = [make_element(level, "Годичный план")]
    return [_entry_from_element(el) for el in items]


class _DragList(QListWidget):
    def startDrag(self, actions):
        item = self.currentItem()
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        mime = QMimeData()
        mime.setText(json.dumps(data, ensure_ascii=False))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class LibraryPanel(QFrame):
    request_add = pyqtSignal(object)   # элемент для добавления на полотно

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("library_panel")
        self.level = HierarchyLevel.EXERCISE

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.title_label = QLabel("Библиотека")
        self.title_label.setObjectName("panel_title")
        root.addWidget(self.title_label)

        self.level_badge = QLabel()
        self.level_badge.setObjectName("level_badge")
        self.level_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.level_badge)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск…")
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tab_my = self._make_list()
        self.tab_presets = self._make_list()
        self.tabs.addTab(self.tab_my, "Мои")
        self.tabs.addTab(self.tab_presets, "Пресеты")
        root.addWidget(self.tabs, 1)

        self.btn_add_empty = QPushButton("＋  Пустой элемент")
        self.btn_add_empty.setObjectName("accent")
        self.btn_add_empty.clicked.connect(self._add_empty)
        root.addWidget(self.btn_add_empty)

        row = QHBoxLayout()
        self.btn_export = QPushButton("Экспорт шаблонов")
        self.btn_import = QPushButton("Импорт шаблонов")
        self.btn_export.setToolTip("Сохранить элементы библиотеки в JSON")
        self.btn_import.setToolTip("Загрузить шаблоны упражнений из JSON (не .tplan)")
        self.btn_export.clicked.connect(self._export)
        self.btn_import.clicked.connect(self._import)
        row.addWidget(self.btn_export)
        row.addWidget(self.btn_import)
        root.addLayout(row)

        self.set_level(self.level)

    def _make_list(self) -> _DragList:
        lst = _DragList()
        lst.setDragEnabled(True)
        lst.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        lst.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        lst.itemDoubleClicked.connect(self._on_double_click)
        return lst

    # ──────────────────────────────────────────────────────────────────
    def set_level(self, level: HierarchyLevel) -> None:
        self.level = level
        self.level_badge.setText(f"Уровень: {LEVEL_NAMES.get(level, '')}")
        item_name = LEVEL_ITEM_NAMES.get(level, "элемент")
        self.btn_add_empty.setText(f"＋  Пустой: {item_name}")
        self._reload()

    def refresh_personal(self) -> None:
        self._fill(self.tab_my, library_store.entries_for_level(self.level), my=True)

    def _reload(self) -> None:
        self._fill(self.tab_presets, _preset_entries(self.level), my=False)
        self.refresh_personal()

    def _fill(self, lst: _DragList, entries: List[Dict], my: bool) -> None:
        lst.clear()
        if not entries:
            placeholder = QListWidgetItem(
                "Пусто — сохраните элемент кнопкой ★" if my else "Нет пресетов")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            lst.addItem(placeholder)
            return
        for entry in entries:
            data = {"kind": "template", "level": entry["level"],
                    "title": entry.get("title", ""), "entry": entry}
            item = QListWidgetItem(entry.get("title", "Без названия"))
            item.setFont(QFont("Segoe UI", 11))
            item.setData(Qt.ItemDataRole.UserRole, data)
            lst.addItem(item)

    def _filter(self, text: str) -> None:
        lst = self.tabs.currentWidget()
        if not isinstance(lst, QListWidget):
            return
        text = text.lower()
        for i in range(lst.count()):
            it = lst.item(i)
            it.setHidden(text not in it.text().lower())

    # ──────────────────────────────────────────────────────────────────
    def _on_double_click(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        element = library_store.build_element(data["entry"])
        self.request_add.emit(element)

    def _add_empty(self) -> None:
        self.request_add.emit(make_element(self.level))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт шаблонов", "templates.json", "JSON (*.json)")
        if path:
            library_store.export_library(path)

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт шаблонов", "", "JSON (*.json)")
        if path:
            try:
                count = library_store.import_library(path)
                self.refresh_personal()
                QMessageBox.information(self, "Импорт",
                                        f"Добавлено шаблонов: {count}")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Ошибка", f"Не удалось импортировать: {exc}")
