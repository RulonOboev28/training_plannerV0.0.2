"""Плавные стрелки-связи между плитками.

Внутри колонки — мягкая вертикаль; между колонками — выход вбок, дуга в
коридоре под плитками (не через тела плиток), затем вход сбоку.
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
WRAP_STUB_MIN = 36.0
WRAP_STUB_MAX = 80.0
EDGE_INSET = 2.5
GUTTER_CORNER = 18.0


class ConnectionItem(QGraphicsItem):
    def __init__(self, source: TileNode, target: TileNode, kind: str = "sequence"):
        super().__init__()
        self.source = source
        self.target = target
        self.kind = kind
        self._path = QPainterPath()
        self._arrow = QPolygonF()
        self._obstacle_nodes: List[TileNode] = []
        self._auto_route = kind in ("auto_down", "auto_wrap")
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_path()

    def set_auto_route(self, enabled: bool) -> None:
        """После ручного сдвига плиток — обычные дуги, как у sequence."""
        self._auto_route = enabled

    def set_obstacles(self, nodes_list: List[TileNode]) -> None:
        self._obstacle_nodes = [
            n for n in nodes_list
            if n is not self.source and n is not self.target
        ]

    def update_path(self) -> None:
        self.prepareGeometryChange()

        sr = self._scene_rect(self.source)
        tr = self._scene_rect(self.target)

        self.setZValue(
            12 if self._auto_route and self.kind in ("auto_down", "auto_wrap") else -1)

        if _use_wrap_path(sr, tr, self.kind, self._auto_route):
            self._build_wrap_path(sr, tr)
            return

        if _use_down_path(sr, tr, self.kind, self._auto_route):
            self._build_down_path(sr, tr)
            return

        anchor_kind = self.kind
        if self.kind in ("auto_down", "auto_wrap") and not self._auto_route:
            anchor_kind = "sequence"
        start, s_normal, end, t_normal = _anchors(sr, tr, anchor_kind)

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

    def _wrap_channel_y(self, sr: QRectF, tr: QRectF) -> float:
        bottom = max(sr.bottom(), tr.bottom())
        x_lo = min(sr.left(), tr.left()) - 8.0
        x_hi = max(sr.right(), tr.right()) + 8.0
        for node in self._obstacle_nodes:
            r = self._scene_rect(node)
            if r.right() < x_lo or r.left() > x_hi:
                continue
            bottom = max(bottom, r.bottom())
        return bottom + AUTO_WRAP_CHANNEL

    def _build_wrap_path(self, sr: QRectF, tr: QRectF) -> None:
        sc, tc = sr.center(), tr.center()
        start = QPointF(sr.right() + EDGE_INSET, sc.y())
        end = QPointF(tr.left() - EDGE_INSET, tc.y())

        span_x = end.x() - start.x()
        if span_x < 24.0:
            self._build_wrap_fallback_cubic(start, end)
            return

        # Переход «вверх» (нижняя плитка колонки → верх следующей): зазор между колонками.
        if tc.y() < sc.y() - nodes.TILE_H * 0.12:
            self._build_wrap_gutter_path(start, end, span_x)
            return

        # Цель ниже или на одном уровне — коридор под плитками.
        self._build_wrap_channel_path(start, end, sr, tr, span_x)

    def _build_wrap_gutter_path(self, start: QPointF, end: QPointF, span_x: float) -> None:
        gutter_x = start.x() + max(WRAP_STUB_MIN, min(WRAP_STUB_MAX, span_x * 0.32))
        gutter_x = min(gutter_x, end.x() - 22.0)
        corner = min(GUTTER_CORNER, abs(end.y() - start.y()) * 0.22, (gutter_x - start.x()) * 0.45)
        corner = max(10.0, corner)
        dy = end.y() - start.y()
        v_sign = 1.0 if dy >= 0 else -1.0

        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(QPointF(gutter_x - corner, start.y()))
        path.quadTo(QPointF(gutter_x, start.y()),
                    QPointF(gutter_x, start.y() + v_sign * corner))
        path.lineTo(QPointF(gutter_x, end.y() - v_sign * corner))
        path.quadTo(QPointF(gutter_x, end.y()),
                    QPointF(gutter_x + corner, end.y()))
        path.lineTo(end)
        self._path = path
        self._arrow = _arrow_head(end, 0.0, ARROW_SIZE)

    def _build_wrap_channel_path(self, start: QPointF, end: QPointF,
                                 sr: QRectF, tr: QRectF, span_x: float) -> None:
        channel_y = self._wrap_channel_y(sr, tr)
        stub = max(WRAP_STUB_MIN, min(WRAP_STUB_MAX, span_x * 0.14))

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(
            QPointF(start.x() + stub * 0.45, start.y()),
            QPointF(start.x() + stub, start.y() + max(28.0, (channel_y - start.y()) * 0.35)),
            QPointF(start.x() + stub, channel_y),
        )
        path.lineTo(QPointF(end.x() - stub, channel_y))
        last_c = QPointF(
            end.x() - stub,
            channel_y + (end.y() - channel_y) * 0.45,
        )
        path.cubicTo(
            QPointF(end.x() - stub, channel_y + max(18.0, (end.y() - channel_y) * 0.2)),
            last_c,
            end,
        )
        self._path = path
        angle = math.atan2(end.y() - last_c.y(), end.x() - last_c.x())
        self._arrow = _arrow_head(end, angle, ARROW_SIZE)

    def _build_wrap_fallback_cubic(self, start: QPointF, end: QPointF) -> None:
        mid = QPointF((start.x() + end.x()) * 0.5, (start.y() + end.y()) * 0.5)
        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(
            QPointF(start.x(), mid.y()),
            QPointF(end.x(), mid.y()),
            end,
        )
        self._path = path
        angle = math.atan2(end.y() - mid.y(), end.x() - mid.x())
        self._arrow = _arrow_head(end, angle, ARROW_SIZE)

    def _build_down_path(self, sr: QRectF, tr: QRectF) -> None:
        sc, tc = sr.center(), tr.center()
        start = QPointF(sc.x(), sr.bottom())
        end = QPointF(tc.x(), tr.top())
        mid_y = (start.y() + end.y()) * 0.5

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(
            QPointF(start.x(), start.y() + (mid_y - start.y()) * 0.55),
            QPointF(end.x(), end.y() - (end.y() - mid_y) * 0.55),
            end,
        )
        self._path = path

        c2 = QPointF(end.x(), end.y() - (end.y() - mid_y) * 0.55)
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


def _use_wrap_path(sr: QRectF, tr: QRectF, kind: str, auto_route: bool) -> bool:
    return auto_route and kind == "auto_wrap"


def _use_down_path(sr: QRectF, tr: QRectF, kind: str, auto_route: bool) -> bool:
    return auto_route and kind == "auto_down"


def _anchors(sr: QRectF, tr: QRectF, kind: str = "sequence") -> Tuple[QPointF, QPointF, QPointF, QPointF]:
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
        col_wrap = dx > nodes.TILE_W * 0.5 and dy < -nodes.TILE_H * 0.5
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
