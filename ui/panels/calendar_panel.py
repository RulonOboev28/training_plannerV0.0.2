"""Нижняя панель календаря: сплошная лента месяцев, прокрутка колёсиком влево/вправо."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QWheelEvent
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.calendar_map import (
    COLOR_CURRENT, COLOR_PARENT, LAYER_CURRENT_ALPHA, LAYER_PARENT_ALPHA,
    MONTH_NAMES_RU, WEEKDAY_NAMES_RU, add_months, build_day_index, iter_plan_days,
    month_grid, parse_plan_start, resolve_calendar_layers,
)
from core.date_cascade import bind_element_start_date

if TYPE_CHECKING:
    from ui.canvas.viewport import CanvasView

_CELL = 36
_PAD = 4
_HEADER = 22
_WDAY = 16
_MONTH_W = 7 * _CELL + 2 * _PAD
_MONTH_H = _HEADER + _WDAY + 6 * _CELL + _PAD
_MONTH_GAP = 10
# Сплошная лента: месяцы до и после текущего фокуса
_MONTHS_BEFORE = 8
_MONTHS_AFTER = 16
_COLLAPSED_H = 38


class CalendarScrollArea(QScrollArea):
    """Горизонтальная прокрутка: колёсико вверх/вниз → влево/вправо."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        if delta == 0:
            event.ignore()
            return
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - int(delta * 0.6))
        event.accept()


class MonthWidget(QWidget):
    """Один месяц: полупрозрачные «ленты» диапазонов + номера дней."""

    day_clicked = pyqtSignal(object, object)

    def __init__(self, year: int, month: int, parent=None):
        super().__init__(parent)
        self._year = year
        self._month = month
        self._cells = month_grid(year, month)
        self._parent_dates: Set[date] = set()
        self._current_dates: Set[date] = set()
        self._day_index = {}
        self._theme = "dark"
        self.setFixedSize(_MONTH_W, _MONTH_H)
        self.setMouseTracking(True)

    def set_month(self, year: int, month: int) -> None:
        if self._year == year and self._month == month:
            return
        self._year = year
        self._month = month
        self._cells = month_grid(year, month)

    def set_layers(self, parent_dates: Set[date], current_dates: Set[date],
                   day_index: dict, theme: str) -> None:
        self._parent_dates = parent_dates
        self._current_dates = current_dates
        self._day_index = day_index
        self._theme = theme
        self.update()

    def _cell_rect(self, row: int, col: int):
        from PyQt6.QtCore import QRectF
        x = _PAD + col * _CELL
        y = _HEADER + _WDAY + row * _CELL
        return QRectF(x, y, _CELL, _CELL)

    def _hit_test(self, pos) -> Optional[date]:
        for i, cell_date in enumerate(self._cells):
            if cell_date is None:
                continue
            row, col = divmod(i, 7)
            r = self._cell_rect(row, col)
            if r.contains(pos.x(), pos.y()):
                return cell_date
        return None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test(event.position())
            if hit is not None:
                self.day_clicked.emit(hit, event.modifiers())
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, CalendarScrollArea):
                parent.wheelEvent(event)
                return
            parent = parent.parentWidget()
        event.ignore()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        title_color = QColor("#e8e4ff" if self._theme == "dark" else "#1d2140")
        p.setPen(title_color)
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.drawText(_PAD, 16, f"{MONTH_NAMES_RU[self._month]} {self._year}")

        wday_color = QColor("#8a86b8" if self._theme == "dark" else "#6a719e")
        p.setPen(wday_color)
        p.setFont(QFont("Segoe UI", 8))
        for col, name in enumerate(WEEKDAY_NAMES_RU):
            p.drawText(int(_PAD + col * _CELL), _HEADER + 12, _CELL, 14,
                       int(Qt.AlignmentFlag.AlignCenter), name)

        self._draw_bands(p, self._parent_dates, COLOR_PARENT, LAYER_PARENT_ALPHA)
        self._draw_bands(p, self._current_dates, COLOR_CURRENT, LAYER_CURRENT_ALPHA)

        for i, cell_date in enumerate(self._cells):
            if cell_date is None:
                continue
            row, col = divmod(i, 7)
            r = self._cell_rect(row, col)
            pd = self._day_index.get(cell_date)
            in_current = cell_date in self._current_dates
            fg = QColor("#ffffff" if self._theme == "dark" else "#1d2140")
            if in_current:
                fg = QColor("#ffffff")
            p.setPen(fg)
            weight = QFont.Weight.Bold if in_current else QFont.Weight.Normal
            p.setFont(QFont("Segoe UI", 10, weight))
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), str(cell_date.day))
            if pd and pd.is_training:
                p.setPen(QColor("#524f9d"))
                cx = int(r.center().x()) + 8
                cy = int(r.center().y()) + 8
                p.drawEllipse(cx, cy, 4, 4)

    def _draw_bands(self, p: QPainter, dates: Set[date], color: str,
                    alpha: float) -> None:
        fill = QColor(color)
        fill.setAlphaF(alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fill)
        for row in range(6):
            for c0, c1 in self._row_segments(row, dates):
                r0 = self._cell_rect(row, c0)
                r1 = self._cell_rect(row, c1)
                band = r0.united(r1).adjusted(1, 1, -1, -1)
                p.drawRoundedRect(band, 6, 6)

    def _row_segments(self, row: int, dates: Set[date]) -> List[Tuple[int, int]]:
        segments: List[Tuple[int, int]] = []
        start_col: Optional[int] = None
        for col in range(7):
            idx = row * 7 + col
            cell = self._cells[idx] if idx < len(self._cells) else None
            in_set = cell is not None and cell in dates
            if in_set:
                if start_col is None:
                    start_col = col
            elif start_col is not None:
                segments.append((start_col, col - 1))
                start_col = None
        if start_col is not None:
            segments.append((start_col, 6))
        return segments


class CalendarPanel(QFrame):
    """Прикреплённая к низу полотна панель — раскрывается вверх."""

    day_selected = pyqtSignal(object)
    date_bound = pyqtSignal(object, object)
    bind_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("calendar_panel")
        self._canvas: Optional[CanvasView] = None
        self._theme = "dark"
        self._expanded = False
        self._month_widgets: List[MonthWidget] = []
        self._month_keys: List[Tuple[int, int]] = []
        self._last_scroll_anchor: Optional[date] = None
        self._build_ui()
        self._apply_height()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 6)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(10)

        self.btn_toggle = QPushButton("▸  Календарь")
        self.btn_toggle.setObjectName("cal_toggle")
        self.btn_toggle.setFlat(True)
        self.btn_toggle.clicked.connect(self.toggle)
        header.addWidget(self.btn_toggle)

        self.lbl_current = QLabel()
        self.lbl_current.setObjectName("cal_scope_micro")
        self.lbl_current.setVisible(False)
        header.addWidget(self.lbl_current)

        self.lbl_parent = QLabel()
        self.lbl_parent.setObjectName("cal_scope_meso")
        self.lbl_parent.setVisible(False)
        header.addWidget(self.lbl_parent)

        header.addStretch(1)

        self.lbl_start = QLabel()
        self.lbl_start.setObjectName("cal_strip")
        header.addWidget(self.lbl_start)

        root.addLayout(header)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._months_scroll = CalendarScrollArea()
        self._months_host = QWidget()
        self._months_host.setFixedHeight(_MONTH_H)
        self._months_layout = QHBoxLayout(self._months_host)
        self._months_layout.setSpacing(_MONTH_GAP)
        self._months_layout.setContentsMargins(0, 0, 0, 0)
        self._months_scroll.setWidget(self._months_host)
        content_layout.addWidget(self._months_scroll)
        self._months_scroll.viewport().installEventFilter(self)

        root.addWidget(self._content)
        self._content.setVisible(False)
        self._set_header_visible(False)

    def _install_wheel_filters(self) -> None:
        self._months_host.installEventFilter(self)
        for mw in self._month_widgets:
            mw.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if self._expanded and event.type() == QEvent.Type.Wheel:
            self._months_scroll.wheelEvent(event)
            return True
        return super().eventFilter(obj, event)

    def bind_canvas(self, canvas: CanvasView) -> None:
        self._canvas = canvas
        canvas.viewport_changed.connect(self._refresh_if_open)
        canvas.level_changed.connect(self._refresh_if_open)
        canvas.plan_changed.connect(self._refresh_if_open)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        if self._expanded:
            self.refresh()

    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._set_header_visible(self._expanded)
        self.btn_toggle.setText(
            "▾  Календарь" if self._expanded else "▸  Календарь")
        self._apply_height()
        if self._expanded:
            self._last_scroll_anchor = None
            self.refresh()
            self._apply_height()

    def open(self) -> None:
        if not self._expanded:
            self.toggle()

    def close_panel(self) -> None:
        if self._expanded:
            self.toggle()

    def _set_header_visible(self, visible: bool) -> None:
        self.lbl_start.setVisible(visible)
        if not visible:
            self.lbl_current.setVisible(False)
            self.lbl_parent.setVisible(False)

    def _apply_height(self) -> None:
        if self._expanded:
            sb_h = self._months_scroll.horizontalScrollBar().sizeHint().height()
            header_h = self.btn_toggle.sizeHint().height()
            margins = self.layout().contentsMargins()
            vert_margin = margins.top() + margins.bottom()
            spacing = self.layout().spacing()
            scroll_h = _MONTH_H + sb_h
            self._months_scroll.setFixedHeight(scroll_h)
            total = vert_margin + header_h + spacing + scroll_h
            self.setFixedHeight(total)
        else:
            self.setFixedHeight(_COLLAPSED_H)

    def _refresh_if_open(self) -> None:
        if self._expanded:
            self.refresh()

    def refresh_if_open(self) -> None:
        self._refresh_if_open()

    def _on_day_clicked(self, on_date: date, modifiers) -> None:
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._try_bind_date(on_date)
            return
        self.day_selected.emit(on_date)
        if self._canvas is not None:
            self._canvas.navigate_to_date(on_date)

    def _try_bind_date(self, on_date: date) -> None:
        if self._canvas is None:
            return
        element = self._canvas.get_selected_element()
        if element is None:
            self.bind_failed.emit("Выберите элемент на полотне")
            return
        err = bind_element_start_date(
            self._canvas.plan, element, on_date,
            area_level=self._canvas.area_level(),
        )
        if err:
            self.bind_failed.emit(err)
            return
        self._canvas.refresh_selected_node()
        self._canvas.commit_state(("date_bind", element.id))
        self._canvas.notify_plan_changed()
        self.date_bound.emit(element, on_date)
        self.refresh()

    def _month_sequence(self, plan, anchor: date) -> List[Tuple[int, int]]:
        """Непрерывная лента месяцев вокруг фокуса и охвата плана."""
        start = parse_plan_start(plan.plan_start_date, plan)
        days = list(iter_plan_days(plan, start))
        if days:
            plan_first = days[0].on_date
            plan_last = days[-1].on_date
            lead = max(_MONTHS_BEFORE, _months_apart(plan_first, anchor))
            trail = max(_MONTHS_AFTER, _months_apart(anchor, plan_last))
        else:
            lead, trail = _MONTHS_BEFORE, _MONTHS_AFTER

        origin = add_months(anchor.year, anchor.month, -lead)
        total = lead + trail + 1
        return [add_months(origin[0], origin[1], i) for i in range(total)]

    def _rebuild_strip(self, month_keys: List[Tuple[int, int]]) -> None:
        if month_keys == self._month_keys and self._month_widgets:
            return

        for mw in self._month_widgets:
            mw.removeEventFilter(self)
            self._months_layout.removeWidget(mw)
            mw.deleteLater()
        self._month_widgets.clear()

        for year, month in month_keys:
            mw = MonthWidget(year, month)
            mw.day_clicked.connect(self._on_day_clicked)
            self._months_layout.addWidget(mw)
            self._month_widgets.append(mw)

        self._month_keys = list(month_keys)
        n = len(month_keys)
        width = max(_MONTH_W, n * _MONTH_W + max(0, n - 1) * _MONTH_GAP)
        self._months_host.setFixedWidth(width)
        self._install_wheel_filters()

    def _scroll_to_date(self, on_date: date) -> None:
        key = (on_date.year, on_date.month)
        if key not in self._month_keys:
            return
        idx = self._month_keys.index(key)
        x = idx * (_MONTH_W + _MONTH_GAP)
        viewport_w = self._months_scroll.viewport().width()
        target = max(0, x - max(0, (viewport_w - _MONTH_W) // 2))
        self._months_scroll.horizontalScrollBar().setValue(target)

    def refresh(self) -> None:
        if self._canvas is None:
            return
        plan = self._canvas.plan
        start = parse_plan_start(plan.plan_start_date, plan)
        layers = resolve_calendar_layers(plan, self._canvas, start)
        day_index = build_day_index(plan, start)

        self.lbl_start.setText(f"Начало: {start.strftime('%d.%m.%Y')}")
        if layers.current_title:
            self.lbl_current.setText(f"Микро · {layers.current_title}")
            self.lbl_current.setVisible(True)
        else:
            self.lbl_current.clear()
            self.lbl_current.setVisible(False)
        if layers.parent_title:
            self.lbl_parent.setText(f"Мезо · {layers.parent_title}")
            self.lbl_parent.setVisible(True)
        else:
            self.lbl_parent.clear()
            self.lbl_parent.setVisible(False)

        month_keys = self._month_sequence(plan, layers.anchor_date)
        self._rebuild_strip(month_keys)

        for mw, (year, month) in zip(self._month_widgets, month_keys):
            mw.set_month(year, month)
            mw.set_layers(
                layers.parent_dates, layers.current_dates, day_index, self._theme)

        if self._last_scroll_anchor != layers.anchor_date:
            self._scroll_to_date(layers.anchor_date)
            self._last_scroll_anchor = layers.anchor_date

        self._apply_height()


def _months_apart(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)
