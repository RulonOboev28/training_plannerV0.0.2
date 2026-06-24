"""Тесты чистой геометрии раскладки (запрет наложений / поиск свободного места)."""
from core.geometry import find_free_slot, rect_intersect, slot_hits

W, H = 300.0, 100.0
STEP = 60.0


def test_rect_intersect_true_and_false():
    assert rect_intersect(0, 0, W, H, 50, 50, W, H) is True
    # вплотную справа — не пересекается
    assert rect_intersect(0, 0, W, H, W, 0, W, H) is False
    # далеко по вертикали
    assert rect_intersect(0, 0, W, H, 0, H + 10, W, H) is False


def test_slot_hits_allows_touching():
    occupied = [(0.0, 0.0)]
    # та же позиция — коллизия
    assert slot_hits(0.0, 0.0, occupied, W, H) is True
    # ровно справа вплотную — допускается (нет наложения)
    assert slot_hits(W, 0.0, occupied, W, H) is False


def test_find_free_slot_returns_same_when_free():
    occupied = [(1000.0, 1000.0)]
    x, y = find_free_slot(120.0, 60.0, occupied, W, H, STEP)
    assert (x, y) == (120.0, 60.0)


def test_find_free_slot_avoids_overlap():
    occupied = [(0.0, 0.0)]
    x, y = find_free_slot(0.0, 0.0, occupied, W, H, STEP)
    # найденная позиция не должна накладываться на занятую
    assert not slot_hits(x, y, occupied, W, H)
    assert x >= 0.0


def test_find_free_slot_respects_min_x():
    occupied = []
    x, y = find_free_slot(-500.0, 0.0, occupied, W, H, STEP, min_x=0.0)
    assert x >= 0.0
