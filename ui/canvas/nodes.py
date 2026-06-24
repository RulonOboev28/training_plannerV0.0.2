"""Плитка элемента и полупрозрачная область-контейнер на полотне.

Плитки располагаются в локальных координатах своей области (area_origin задаёт
смещение области в сцене). Несколько областей-соседей показываются одновременно.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QGraphicsItem, QStyle

from core.models import HierarchyLevel, element_color

TILE_W = 300.0
TILE_H = 100.0
TILE_RADIUS = 16.0

# Пресеты размера плиток (подпись -> (ширина, высота)).
TILE_SIZES = {
    "Компактные": (240.0, 84.0),
    "Обычные": (300.0, 100.0),
    "Крупные": (372.0, 124.0),
}


def set_tile_size(width: float, height: float) -> None:
    """Меняет глобальный размер плиток. Полотно должно перерисоваться после."""
    global TILE_W, TILE_H, TILE_RADIUS
    TILE_W = float(width)
    TILE_H = float(height)
    TILE_RADIUS = max(10.0, height * 0.16)


class TileNode(QGraphicsItem):
    """Плитка одного элемента. Логический размер фиксирован (300×100)."""

    def __init__(self, element, level: HierarchyLevel, view):
        super().__init__()
        self.element = element
        self.level = level
        self._view = view
        self._is_source = False

        # принадлежность области
        self.area_id = None
        self.area_origin = QPointF(0.0, 0.0)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, TILE_W + 4, TILE_H + 4)

    def rect(self) -> QRectF:
        return QRectF(0, 0, TILE_W, TILE_H)

    def center_scene(self) -> QPointF:
        return self.mapToScene(QPointF(TILE_W / 2, TILE_H / 2))

    def set_connection_source(self, value: bool) -> None:
        self._is_source = value
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        base = QColor(element_color(self.element))
        rect = self.rect()

        path = QPainterPath()
        path.addRoundedRect(rect, TILE_RADIUS, TILE_RADIUS)

        shadow = QColor(0, 0, 0, 80)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(rect.translated(0, 5), TILE_RADIUS, TILE_RADIUS)
        painter.fillPath(shadow_path, shadow)

        gradient = QLinearGradient(0, 0, 0, TILE_H)
        gradient.setColorAt(0.0, base.lighter(120))
        gradient.setColorAt(1.0, base.darker(110))
        painter.fillPath(path, QBrush(gradient))

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if self._is_source:
            pen = QPen(QColor("#ffd166"), 3.5)
        elif selected:
            pen = QPen(QColor("#ffffff"), 3.0)
        else:
            pen = QPen(QColor(255, 255, 255, 50), 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setPen(QColor("#ffffff"))
        title_font = QFont("Segoe UI", 17)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(18, 16, TILE_W - 36, 40),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            _elide(self.element.title, 24),
        )

        painter.setPen(QColor(255, 255, 255, 210))
        painter.setFont(QFont("Segoe UI", 11))
        subtitle = self.element.subtitle() if hasattr(self.element, "subtitle") else ""
        painter.drawText(
            QRectF(18, 56, TILE_W - 36, 30),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            _elide(subtitle, 34),
        )

    # — взаимодействие —
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._view:
            return self._view.constrain_tile_point(self, QPointF(value))
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self._view:
            self._view.on_node_moved(self)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._view:
            self._view.on_tile_released(self)


class ContainerArea(QGraphicsItem):
    """Полупрозрачная область-контейнер с дочерними плитками внутри."""

    def __init__(self, element, rect: QRectF, color: str, active: bool = False):
        super().__init__()
        self.element = element
        self._rect = rect
        self._color = QColor(color)
        self._active = active
        self.setZValue(-5)

    def set_rect(self, rect: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = rect
        self.update()

    def set_active(self, value: bool) -> None:
        if self._active != value:
            self._active = value
            self.update()

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-4, -4, 4, 4)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(self._rect, 24, 24)

        fill = QColor(self._color)
        fill.setAlpha(40 if self._active else 24)
        painter.fillPath(path, fill)

        c = self._color
        border_alpha = 180 if self._active else 90
        pen = QPen(QColor(c.red(), c.green(), c.blue(), border_alpha),
                   2.0 if self._active else 1.4, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setPen(QColor(255, 255, 255, 150 if self._active else 110))
        font = QFont("Segoe UI", 13)
        font.setItalic(True)
        font.setBold(self._active)
        painter.setFont(font)
        title = self.element.title if self.element else ""
        painter.drawText(
            QRectF(self._rect.left() + 18, self._rect.top() + 10,
                   self._rect.width() - 36, 30),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            title,
        )


def _elide(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"
