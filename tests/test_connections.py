"""Тесты геометрии стрелок-связей: откуда выходят и куда входят."""
from PyQt6.QtCore import QRectF

from ui.canvas import nodes
from ui.canvas.connections import _anchors


def test_horizontal_exits_right_edge(qapp):
    sr = QRectF(0.0, 0.0, nodes.TILE_W, nodes.TILE_H)
    tr = QRectF(nodes.TILE_W + 200.0, 0.0, nodes.TILE_W, nodes.TILE_H)
    start, s_normal, end, t_normal = _anchors(sr, tr)
    assert start.x() == sr.right()
    assert (s_normal.x(), s_normal.y()) == (1.0, 0.0)
    # цель справа — вход в левый край
    assert end.x() == tr.left()
    assert (t_normal.x(), t_normal.y()) == (-1.0, 0.0)


def test_offset_down_still_exits_right(qapp):
    sr = QRectF(0.0, 0.0, nodes.TILE_W, nodes.TILE_H)
    tr = QRectF(nodes.TILE_W + 200.0, 240.0, nodes.TILE_W, nodes.TILE_H)
    start, s_normal, _end, _t = _anchors(sr, tr)
    assert (s_normal.x(), s_normal.y()) == (1.0, 0.0)
    assert start.x() == sr.right()


def test_stacked_below_exits_bottom(qapp):
    sr = QRectF(0.0, 0.0, nodes.TILE_W, nodes.TILE_H)
    tr = QRectF(0.0, nodes.TILE_H + 200.0, nodes.TILE_W, nodes.TILE_H)
    start, s_normal, end, t_normal = _anchors(sr, tr)
    assert (s_normal.x(), s_normal.y()) == (0.0, 1.0)
    assert start.y() == sr.bottom()
    assert (t_normal.x(), t_normal.y()) == (0.0, -1.0)
    assert end.y() == tr.top()


def test_column_wrap_exits_bottom_to_top_for_manual_sequence(qapp):
    step_x = nodes.TILE_W + 90.0
    step_y = nodes.TILE_H + 80.0
    sr = QRectF(0.0, 2 * step_y, nodes.TILE_W, nodes.TILE_H)
    tr = QRectF(step_x, 0.0, nodes.TILE_W, nodes.TILE_H)
    start, s_normal, end, t_normal = _anchors(sr, tr, kind="sequence")
    assert (s_normal.x(), s_normal.y()) == (0.0, 1.0)
    assert start.y() == sr.bottom()
    assert (t_normal.x(), t_normal.y()) == (0.0, -1.0)
    assert end.y() == tr.top()


def test_auto_wrap_uses_side_anchors(qapp):
    step_x = nodes.TILE_W + 90.0
    step_y = nodes.TILE_H + 80.0
    sr = QRectF(0.0, 2 * step_y, nodes.TILE_W, nodes.TILE_H)
    tr = QRectF(step_x, 0.0, nodes.TILE_W, nodes.TILE_H)
    start, s_normal, end, t_normal = _anchors(sr, tr, kind="auto_wrap")
    assert start.x() == sr.right()
    assert end.x() == tr.left()
    assert (s_normal.x(), s_normal.y()) == (1.0, 0.0)
    assert (t_normal.x(), t_normal.y()) == (-1.0, 0.0)
    assert start.y() == sr.center().y()
    assert end.y() == tr.center().y()


def test_stacked_above_exits_top(qapp):
    sr = QRectF(0.0, 400.0, nodes.TILE_W, nodes.TILE_H)
    tr = QRectF(0.0, 0.0, nodes.TILE_W, nodes.TILE_H)
    start, s_normal, _end, _t = _anchors(sr, tr)
    assert (s_normal.x(), s_normal.y()) == (0.0, -1.0)
    assert start.y() == sr.top()
