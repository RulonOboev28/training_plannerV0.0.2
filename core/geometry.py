"""Чистая геометрия раскладки плиток (без зависимости от Qt).

Вынесено отдельно, чтобы логику запрета наложений и поиска свободного места
можно было покрыть юнит-тестами без графического окружения.
Все координаты — локальные внутри области, плитки одинакового размера (w×h).
"""
from __future__ import annotations

from typing import Iterable, List, Tuple


def rect_intersect(ax: float, ay: float, aw: float, ah: float,
                   bx: float, by: float, bw: float, bh: float) -> bool:
    """Пересекаются ли два прямоугольника (касание краёв не считается)."""
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def slot_hits(x: float, y: float, occupied: Iterable[Tuple[float, float]],
              w: float, h: float, shrink: float = 2.0) -> bool:
    """Накрывает ли плитка в (x, y) какую-либо из занятых позиций.

    `shrink` слегка ужимает проверяемый прямоугольник, чтобы соседство впритык
    (без наложения) не считалось коллизией.
    """
    ax, ay = x + shrink, y + shrink
    aw, ah = w - 2 * shrink, h - 2 * shrink
    for ox, oy in occupied:
        if rect_intersect(ax, ay, aw, ah, ox, oy, w, h):
            return True
    return False


def find_free_slot(x: float, y: float, occupied: List[Tuple[float, float]],
                   w: float, h: float, step: float,
                   span: int = 14, min_x: float = 0.0) -> Tuple[float, float]:
    """Ближайшая к (x, y) позиция по сетке `step`, не накладывающаяся на occupied."""
    if x >= min_x and not slot_hits(x, y, occupied, w, h):
        return max(min_x, x), y
    candidates = []
    for ix in range(-span, span + 1):
        for iy in range(-span, span + 1):
            cx = x + ix * step
            cy = y + iy * step
            if cx < min_x:
                continue
            candidates.append((ix * ix + iy * iy, cx, cy))
    candidates.sort(key=lambda c: c[0])
    for _, cx, cy in candidates:
        if not slot_hits(cx, cy, occupied, w, h):
            return cx, cy
    return max(min_x, x), y
