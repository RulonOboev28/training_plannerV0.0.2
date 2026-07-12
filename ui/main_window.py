"""Главное окно: компоновка трёх зон, тулбар, навигация по уровням."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QInputDialog, QLabel, QMainWindow,
    QMenu, QMessageBox, QPushButton, QSlider, QSplitter, QStatusBar, QToolBar,
    QVBoxLayout, QWidget,
)

from core import database, exporting, library_store
from core.paths import resource_path
from core.models import (
    AnnualPlan, HierarchyLevel, LEVEL_ITEM_NAMES, LEVEL_NAMES, Macrocycle,
    Mesocycle, Microcycle, TrainingPlan, Workout,
)
from ui.canvas import nodes
from ui.canvas.viewport import CanvasView
from ui.panels.calendar_panel import CalendarPanel
from ui.panels.library_panel import LibraryPanel
from ui.panels.properties_panel import PropertiesPanel

STYLES_DIR = resource_path("assets", "styles")
THEME_FILES = {"dark": "dark_theme.qss", "light": "light_theme.qss"}


def build_scaffold_plan() -> TrainingPlan:
    """Создаёт пустой план с одной веткой контейнеров до тренировки."""
    workout = Workout(title="Тренировка 1")
    micro = Microcycle(title="Микроцикл 1", workouts=[workout])
    meso = Mesocycle(title="Мезоцикл 1", microcycles=[micro])
    macro = Macrocycle(title="Макроцикл 1", mesocycles=[meso])
    annual = AnnualPlan(title="Годичный план", macrocycles=[macro])
    return TrainingPlan(annual=annual)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Конструктор тренировочного плана")
        self.setMinimumSize(1200, 760)
        self.resize(1500, 920)

        self.theme = "dark"
        self.canvas = CanvasView()
        self.calendar = CalendarPanel()
        self.library = LibraryPanel()
        self.properties = PropertiesPanel()

        self._build_toolbar()
        self._build_layout()
        self._build_statusbar()
        self._connect()
        self._apply_theme(self.theme)

        self._load_initial_plan()

    # ──────────────────────────────────────────────────────────────────
    def _build_layout(self) -> None:
        canvas_wrap = QWidget()
        canvas_layout = QVBoxLayout(canvas_wrap)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self.canvas, 1)
        canvas_layout.addWidget(self.calendar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.library)
        splitter.addWidget(canvas_wrap)
        splitter.addWidget(self.properties)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 940, 320])
        self.library.setMinimumWidth(230)
        self.properties.setMinimumWidth(280)
        self.setCentralWidget(splitter)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Главная")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addWidget(self._btn("Новый", self._new_plan))
        tb.addWidget(self._btn("Открыть", self._open_plan))
        tb.addWidget(self._btn("Сохранить", self._save_plan))
        tb.addSeparator()

        self.btn_undo = self._btn("↶ Отмена", self.canvas.undo)
        self.btn_redo = self._btn("↷ Повтор", self.canvas.redo)
        tb.addWidget(self.btn_undo)
        tb.addWidget(self.btn_redo)
        tb.addSeparator()

        tb.addWidget(self._btn("⧉ Дублировать", self.canvas.duplicate_selection))
        tb.addWidget(self._btn("⊞ Авто-расстановка", self.canvas.auto_layout))
        tb.addSeparator()

        tb.addWidget(self._btn("▲ Вверх", self.canvas.go_up))
        self.btn_new_area = self._btn("＋ Область", self.canvas.create_area)
        tb.addWidget(self.btn_new_area)
        self.btn_calendar = self._btn("📅 Календарь", self._open_calendar)
        tb.addWidget(self.btn_calendar)
        tb.addSeparator()

        self.btn_export = QPushButton("Экспорт ▾")
        export_menu = QMenu(self.btn_export)
        export_menu.addAction("План в файл (.tplan)", self._export_plan)
        export_menu.addAction("Открыть план из файла...", self._import_plan)
        export_menu.addSeparator()
        export_menu.addAction("Полотно в PNG", self._export_png)
        export_menu.addAction("Полотно в PDF", self._export_pdf)
        export_menu.addAction("Таблица в CSV", self._export_csv)
        self.btn_export.setMenu(export_menu)
        tb.addWidget(self.btn_export)
        tb.addWidget(self._btn("История", self._open_history))
        tb.addSeparator()

        self.snap_check = QCheckBox("Привязка")
        self.snap_check.setChecked(True)
        self.snap_check.toggled.connect(self.canvas.set_snap)
        tb.addWidget(self.snap_check)
        tb.addSeparator()

        tb.addWidget(QLabel(" Размер "))
        self.size_combo = QComboBox()
        self.size_combo.addItems(list(nodes.TILE_SIZES.keys()))
        self.size_combo.setCurrentText("Обычные")
        self.size_combo.currentTextChanged.connect(self._on_tile_size)
        tb.addWidget(self.size_combo)

        self.btn_theme = self._btn("Тема: Тёмная", self._toggle_theme)
        tb.addWidget(self.btn_theme)
        tb.addSeparator()

        tb.addWidget(QLabel(" Масштаб "))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(50)
        self.zoom_slider.setMaximum(200)
        self.zoom_slider.setValue(200)
        self.zoom_slider.setFixedWidth(180)
        self.zoom_slider.valueChanged.connect(self._on_slider)
        tb.addWidget(self.zoom_slider)

        self.level_label = QLabel()
        self.level_label.setObjectName("level_label")
        self.level_label.setMinimumWidth(240)
        tb.addWidget(self.level_label)

        tb.addSeparator()
        tb.addWidget(QLabel(" Стадия "))
        for value in range(1, 6):
            area_lvl = HierarchyLevel(value + 1)
            b = QPushButton(str(value))
            b.setFixedWidth(30)
            b.setToolTip(LEVEL_NAMES[area_lvl])
            b.clicked.connect(lambda _=False, v=value: self.canvas.go_to_tile_level(v))
            tb.addWidget(b)

    def _btn(self, text: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(lambda: slot())
        return b

    def _build_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.save_label = QLabel("—")
        self.save_label.setObjectName("save_label")
        self.status.addPermanentWidget(self.save_label)
        self.status.showMessage("Готов к работе")

    def _connect(self) -> None:
        self.canvas.node_selected.connect(self.properties.set_element)
        self.canvas.node_deselected.connect(self.properties.show_placeholder)
        self.canvas.level_changed.connect(self._on_level_changed)
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
        self.canvas.plan_changed.connect(self._on_plan_changed)
        self.canvas.history_changed.connect(self._on_history_changed)
        self.canvas.save_to_library_requested.connect(self._on_save_to_library)

        self.calendar.bind_canvas(self.canvas)
        self.calendar.day_selected.connect(self._on_calendar_day)
        self.calendar.date_bound.connect(self._on_calendar_date_bound)
        self.calendar.bind_failed.connect(self._on_calendar_bind_failed)

        self.properties.bind_canvas(self.canvas)

        self.properties.data_changed.connect(self._on_data_changed)
        self.properties.save_to_library.connect(self._on_save_to_library)

        self.library.request_add.connect(self._on_request_add)

    # ──────────────────────────────────────────────────────────────────
    def _load_initial_plan(self) -> None:
        plan = database.load_autosave()
        if plan is None:
            plan = build_scaffold_plan()
            self.status.showMessage("Создан новый план")
        else:
            self.status.showMessage("Восстановлена прошлая сессия")
        self.canvas.load_plan(plan)
        self._update_level_label()
        self._on_history_changed()
        self._mark_saved()

    def _apply_theme(self, theme: str) -> None:
        self.theme = theme
        path = STYLES_DIR / THEME_FILES.get(theme, THEME_FILES["dark"])
        try:
            self.setStyleSheet(path.read_text(encoding="utf-8"))
        except OSError:
            pass
        self.canvas.set_theme(theme)
        self.calendar.set_theme(theme)
        self.btn_theme.setText("Тема: Светлая" if theme == "light" else "Тема: Тёмная")

    def _toggle_theme(self) -> None:
        self._apply_theme("light" if self.theme == "dark" else "dark")

    def _on_tile_size(self, name: str) -> None:
        size = nodes.TILE_SIZES.get(name)
        if size:
            self.canvas.apply_tile_size(*size)

    # ── обработчики сигналов полотна ──
    def _on_level_changed(self, area_level: HierarchyLevel) -> None:
        self.library.set_level(self.canvas.tile_level())
        item_name = LEVEL_ITEM_NAMES.get(area_level, "область")
        self.btn_new_area.setText(f"＋ {item_name.capitalize()}")
        self.btn_new_area.setEnabled(self.canvas.scope_id is not None)
        self.properties.show_placeholder()
        self._update_level_label()

    def _on_zoom_changed(self, percent: int) -> None:
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(max(50, min(200, percent)))
        self.zoom_slider.blockSignals(False)
        self._update_level_label()

    def _on_history_changed(self) -> None:
        self.btn_undo.setEnabled(self.canvas.can_undo())
        self.btn_redo.setEnabled(self.canvas.can_redo())

    def _on_plan_changed(self) -> None:
        database.save_autosave(self.canvas.plan)
        self._mark_saved()

    def _on_data_changed(self, element) -> None:
        self.canvas.refresh_selected_node()
        self.canvas.commit_state(("edit", getattr(element, "id", None)))
        database.save_autosave(self.canvas.plan)
        self.canvas.notify_plan_changed()
        self._mark_saved()

    def _mark_saved(self) -> None:
        self.save_label.setText("Сохранено • " + datetime.now().strftime("%H:%M:%S"))

    def _on_save_to_library(self, element) -> None:
        library_store.add_element(element)
        self.library.refresh_personal()
        self.status.showMessage(f"Сохранено в библиотеку: {element.title}")

    def _on_request_add(self, element) -> None:
        self.canvas.create_tile(element)
        self.status.showMessage(f"Добавлено: {element.title}")

    def _on_calendar_day(self, on_date) -> None:
        self.status.showMessage(f"Переход к {on_date.strftime('%d.%m.%Y')}")

    def _on_calendar_date_bound(self, element, on_date) -> None:
        self.status.showMessage(
            f"Привязано: {element.title} → {on_date.strftime('%d.%m.%Y')}")

    def _on_calendar_bind_failed(self, message: str) -> None:
        self.status.showMessage(message)

    def _open_calendar(self) -> None:
        self.calendar.toggle()

    def _on_slider(self, value: int) -> None:
        self.canvas.set_percent(value)
        self._update_level_label()

    def _update_level_label(self) -> None:
        area_level = self.canvas.area_level()
        percent = self.canvas.current_percent()
        self.level_label.setText(
            f"Стадия: {LEVEL_NAMES[area_level]} · {percent}%")

    # ── действия тулбара ──
    def _new_plan(self) -> None:
        if QMessageBox.question(
            self, "Новый план",
            "Создать новый план? Несохранённые изменения будут потеряны.",
        ) == QMessageBox.StandardButton.Yes:
            self.canvas.load_plan(build_scaffold_plan())
            database.save_autosave(self.canvas.plan)
            self._update_level_label()
            self._on_history_changed()
            self.status.showMessage("Создан новый план")

    def _open_plan(self) -> None:
        plans = database.list_plans()
        if plans:
            items = ["Выбрать файл (.tplan)..."] + plans
            choice, ok = QInputDialog.getItem(
                self, "Открыть план", "План:", items, 0, False)
            if not ok:
                return
            if choice == items[0]:
                self._open_plan_from_file()
                return
            plan = database.load_plan(choice)
            if plan:
                self._load_plan(plan, f"Открыт план: {choice}")
            return
        self._open_plan_from_file()

    def _open_plan_from_file(self) -> None:
        desktop = str(Path.home() / "Desktop")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть план",
            desktop,
            "План тренировок (*.tplan);;JSON (*.json);;Все файлы (*.*)",
        )
        if not path:
            return
        plan = database.import_plan(path)
        if plan:
            self._load_plan(plan, f"Открыт: {Path(path).name}")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось открыть файл.")

    def _load_plan(self, plan: TrainingPlan, message: str) -> None:
        self.canvas.load_plan(plan)
        database.save_autosave(self.canvas.plan)
        self._update_level_label()
        self._on_history_changed()
        self.status.showMessage(message)

    def _save_plan(self) -> None:
        name, ok = QInputDialog.getText(self, "Сохранить план", "Название:")
        if ok and name:
            path = database.save_plan(name, self.canvas.plan)
            self.status.showMessage(f"Сохранено: {path}")

    def _export_plan(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт плана", "plan.tplan", "Training Plan (*.tplan)")
        if path:
            database.export_plan(path, self.canvas.plan)
            self.status.showMessage(f"Экспортировано: {path}")

    def _import_plan(self) -> None:
        self._open_plan_from_file()

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в PNG", "plan.png", "PNG (*.png)")
        if path:
            self.canvas.export_image(path)
            self.status.showMessage(f"Изображение сохранено: {path}")

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в PDF", "plan.pdf", "PDF (*.pdf)")
        if path:
            self.canvas.export_pdf(path)
            self.status.showMessage(f"PDF сохранён: {path}")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт таблицы", "plan.csv", "CSV (*.csv)")
        if path:
            exporting.write_csv(path, self.canvas.plan)
            self.status.showMessage(f"Таблица сохранена: {path}")

    def _open_history(self) -> None:
        history = database.list_history()
        if not history:
            QMessageBox.information(self, "История", "История версий пуста.")
            return
        labels = [label for _, label in history]
        choice, ok = QInputDialog.getItem(
            self, "История версий",
            "Выберите версию для восстановления:", labels, 0, False)
        if not ok or not choice:
            return
        name = next((n for n, label in history if label == choice), None)
        if name is None:
            return
        plan = database.load_history(name)
        if plan is None:
            QMessageBox.warning(self, "История", "Не удалось загрузить версию.")
            return
        self.canvas.load_plan(plan)
        database.save_autosave(self.canvas.plan)
        self._update_level_label()
        self._on_history_changed()
        self.status.showMessage(f"Восстановлена версия: {choice}")

    def closeEvent(self, event):
        try:
            database.save_autosave(self.canvas.plan)
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)
