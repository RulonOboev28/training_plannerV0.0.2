"""Плавные дугообразные стрелки-связи между плитками.

Стрелка по умолчанию выходит из ПРАВОГО края плитки-источника и плавно
изгибается к цели. Если цель расположена прямо над источником или под ним
(параллельно, в том же «столбце») — стрелка выходит из верхнего/нижнего края.
При авто-расстановке: внутри колонки — стрелка вниз; между колонками — сбоку,
дуга проходит под плитками.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem

from ui.canvas import nodes
from ui.canvas.nodes import TileNode

ARROW_SIZE = 13.0
AUTO_WRAP_CHANNEL = 55.0


class ConnectionItem(QGraphicsItem):
    def __init__(self, source: TileNode, target: TileNode, kind: str = "sequence"):
        super().__init__()
        self.source = source
        self.target = target
        self.kind = kind
        self._path = QPainterPath()
        self._arrow = QPolygonF()
        self.setZValue(-1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_path()

    def set_obstacles(self, nodes: List[TileNode]) -> None:
        return

    def update_path(self) -> None:
        self.prepareGeometryChange()

        sr = self._scene_rect(self.source)
        tr = self._scene_rect(self.target)

        if self.kind == "auto_wrap":
            self._build_auto_wrap_path(sr, tr)
            return

        start, s_normal, end, t_normal = _anchors(sr, tr, self.kind)

        dist = math.hypot(end.x() - start.x(), end.y() - start.y())
        k = max(45.0, min(170.0, dist * 0.45))
        c1 = QPointF(start.x() + s_normal.x() * k, start.y() + s_normal.y() * k)
        c2 = QPointF(end.x() + t_normal.x() * k, end.y() + t_normal.y() * k)

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(c1, c2, end)
        self._path = path

        angle = math.atan2(end.y() - c2.y(), end.x() - c2.x())
        self._arrow = _arrow_head(end, angle, ARROW_SIZE)

    def _build_auto_wrap_path(self, sr: QRectF, tr: QRectF) -> None:
        sc, tc = sr.center(), tr.center()
        start = QPointF(sr.right(), sc.y())
        end = QPointF(tr.left(), tc.y())
        channel_y = max(sr.bottom(), tr.bottom()) + AUTO_WRAP_CHANNEL
        bulge = max(60.0, (end.x() - start.x()) * 0.22)

        path = QPainterPath()
        path.moveTo(start)
        c1 = QPointF(start.x() + bulge, channel_y)
        c2 = QPointF(end.x() - bulge, channel_y)
        path.cubicTo(c1, c2, end)
        self._path = path

        angle = math.atan2(end.y() - c2.y(), end.x() - c2.x())
        self._arrow = _arrow_head(end, angle, ARROW_SIZE)

    @staticmethod
    def _scene_rect(node: TileNode) -> QRectF:
        top_left = node.mapToScene(QPointF(0.0, 0.0))
        return QRectF(top_left.x(), top_left.y(), nodes.TILE_W, nodes.TILE_H)

    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().adjusted(
            -ARROW_SIZE, -ARROW_SIZE, ARROW_SIZE, ARROW_SIZE)

    def shape(self) -> QPainterPath:
        return self._path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#8a93e6") if self.kind in ("sequence", "auto_down", "auto_wrap") else QColor("#b07fd0")
        if self.isSelected():
            color = QColor("#c6515c")

        pen = QPen(color, 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(self._arrow)


def _anchors(sr: QRectF, tr: QRectF, kind: str = "sequence") -> Tuple[QPointF, QPointF, QPointF, QPointF]:
    """Точки выхода/входа стрелки и внешние нормали соответствующих рёбер."""
    sc, tc = sr.center(), tr.center()
    dx = tc.x() - sc.x()
    dy = tc.y() - sc.y()

    if kind == "auto_down":
        start = QPointF(sc.x(), sr.bottom())
        s_normal = QPointF(0.0, 1.0)
        end = QPointF(tc.x(), tr.top())
        t_normal = QPointF(0.0, -1.0)
        return start, s_normal, end, t_normal

    if kind == "sequence":
        col_wrap = (dx > nodes.TILE_W * 0.5 and dy < -nodes.TILE_H * 0.5)
        if col_wrap:
            start = QPointF(sc.x(), sr.bottom())
            s_normal = QPointF(0.0, 1.0)
            end = QPointF(tc.x(), tr.top())
            t_normal = QPointF(0.0, -1.0)
            return start, s_normal, end, t_normal

    stacked = abs(dx) <= nodes.TILE_W * 0.5 and abs(dy) > nodes.TILE_H * 0.5
    if stacked:
        if dy >= 0:
            start = QPointF(sc.x(), sr.bottom())
            s_normal = QPointF(0.0, 1.0)
            end = QPointF(tc.x(), tr.top())
            t_normal = QPointF(0.0, -1.0)
        else:
            start = QPointF(sc.x(), sr.top())
            s_normal = QPointF(0.0, -1.0)
            end = QPointF(tc.x(), tr.bottom())
            t_normal = QPointF(0.0, 1.0)
        return start, s_normal, end, t_normal

    start = QPointF(sr.right(), sc.y())
    s_normal = QPointF(1.0, 0.0)
    if tc.x() >= sc.x():
        end = QPointF(tr.left(), tc.y())
        t_normal = QPointF(-1.0, 0.0)
    else:
        end = QPointF(tr.right(), tc.y())
        t_normal = QPointF(1.0, 0.0)
    return start, s_normal, end, t_normal


def _arrow_head(tip: QPointF, angle: float, size: float) -> QPolygonF:
    spread = math.radians(24)
    p1 = QPointF(tip.x() - size * math.cos(angle - spread),
                 tip.y() - size * math.sin(angle - spread))
    p2 = QPointF(tip.x() - size * math.cos(angle + spread),
                 tip.y() - size * math.sin(angle + spread))
    return QPolygonF([tip, p1, p2])
