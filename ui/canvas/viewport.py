"""Полотно конструктора.

Модель отображения: на «стадии» одновременно показываются ВСЕ соседние области
(контейнеры одного уровня), а внутри каждой — её дочерние плитки. Так можно
видеть и редактировать соседние тренировки/микроциклы, не выходя на уровень выше.

scope_id   — контейнер, чьи дети показываются как области (None = корень → одна
             область «Годичный план»).
area_level — уровень областей (контейнеров-рамок).
tile_level — уровень плиток внутри областей (на 1 ниже area_level).
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QMenu

from core.geometry import find_free_slot
from core.models import (
    HierarchyLevel, TrainingPlan, clone_element, element_color, get_children,
    level_of, make_element,
)
from ui.canvas import nodes
from ui.canvas.connections import ConnectionItem
from ui.canvas.nodes import ContainerArea, TileNode

SCALE_MAX = 1.0
SCALE_MIN = 0.6

GRID = 60.0
SNAP_RADIUS = 22.0

# Геометрия областей
AREA_TOP = -170.0
AREA_H = 340.0
HEADER = 48.0
PAD = 40.0
AREA_GAP = 80.0
TILE_GAP = 50.0

BG_COLOR = "#0b0718"

# Минимальная и максимальная стадия (уровень плиток)
MIN_TILE_LEVEL = 1   # Упражнения
MAX_TILE_LEVEL = 5   # Макроциклы (область — Годичный план)

# Темы оформления полотна (фон + цвет точечной сетки RGBA)
THEMES = {
    "dark": {"bg": "#0b0718", "grid": (255, 255, 255, 24)},
    "light": {"bg": "#eef1fb", "grid": (40, 40, 90, 46)},
}

HISTORY_LIMIT = 80


def _area_min_w() -> float:
    return nodes.TILE_W + 2 * PAD


class CanvasView(QGraphicsView):
    plan_changed = pyqtSignal()
    node_selected = pyqtSignal(object)
    node_deselected = pyqtSignal()
    level_changed = pyqtSignal(object)   # area_level (HierarchyLevel)
    zoom_changed = pyqtSignal(int)
    history_changed = pyqtSignal()
    save_to_library_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        self._bg_color = QColor(THEMES["dark"]["bg"])
        self._grid_color = QColor(*THEMES["dark"]["grid"])
        self.setBackgroundBrush(QBrush(self._bg_color))
        self.setAcceptDrops(True)

        self.plan = TrainingPlan()
        self.scope_id: Optional[str] = None
        self.active_area_id: Optional[str] = None
        self.tile_scale = SCALE_MAX
        self.snap_enabled = True
        self.animations_enabled = True

        self._nodes: Dict[str, TileNode] = {}
        self._connections: List[ConnectionItem] = []
        self._areas: Dict[str, ContainerArea] = {}
        self._area_origin: Dict[str, QPointF] = {}
        self._area_rects: Dict[str, QRectF] = {}
        self._source_node: Optional[TileNode] = None

        self._panning = False
        self._pan_last = QPointF()
        self._lmb_press = QPointF()
        self._lmb_moved = False
        self._relaying = False
        self._drag_dirty = False

        # Память положения камеры между уровнями.
        self._scope_focus: Dict[Optional[str], str] = {}
        self._pending_focus_id: Optional[str] = None
        self._focus_requested = False
        self._focus_zoom_in = True
        self._cam_anim: Optional[QVariantAnimation] = None

        # Буфер обмена (копии элементов) и история (undo/redo).
        self._clipboard: List = []
        self._clipboard_level: int = -1
        self._history: List[dict] = []
        self._hist_index = -1
        self._coalesce_key = None

        self._scene.selectionChanged.connect(self._on_selection_changed)

    # ──────────────────────────────────────────────────────────────────
    # Уровни / области
    # ──────────────────────────────────────────────────────────────────
    def tile_level(self) -> HierarchyLevel:
        if self.scope_id is None:
            return HierarchyLevel(MAX_TILE_LEVEL)
        scope = self.plan.get(self.scope_id)
        if scope is None:
            return HierarchyLevel(MAX_TILE_LEVEL)
        return HierarchyLevel(max(1, level_of(scope).value - 2))

    def area_level(self) -> HierarchyLevel:
        return HierarchyLevel(self.tile_level().value + 1)

    def _areas_list(self) -> List:
        if self.scope_id is None:
            return [self.plan.annual]
        return self.plan.children_of(self.scope_id)

    # ──────────────────────────────────────────────────────────────────
    # Загрузка плана
    # ──────────────────────────────────────────────────────────────────
    def load_plan(self, plan: TrainingPlan) -> None:
        self.plan = plan
        self.tile_scale = SCALE_MAX
        first_micro = self._first_of_level(HierarchyLevel.MICROCYCLE)
        self.scope_id = first_micro.id if first_micro else None
        self.active_area_id = None
        self._scope_focus.clear()
        self._reset_history()
        self._render()

    def _first_of_level(self, level: HierarchyLevel):
        node = self.plan.annual
        guard = 0
        while node is not None and guard < 10:
            guard += 1
            if level_of(node) == level:
                return node
            children = get_children(node)
            if not children:
                return None
            node = children[0]
        return None

    # ──────────────────────────────────────────────────────────────────
    # Рендер
    # ──────────────────────────────────────────────────────────────────
    def _render(self) -> None:
        self._scene.blockSignals(True)
        self._scene.clear()
        self._scene.blockSignals(False)
        self._nodes.clear()
        self._connections.clear()
        self._areas.clear()
        self._area_origin.clear()
        self._area_rects.clear()
        self._source_node = None

        areas = self._areas_list()
        if areas and (self.active_area_id is None
                      or self.active_area_id not in {a.id for a in areas}):
            self.active_area_id = areas[0].id

        running_x = 0.0
        for area_el in areas:
            children = get_children(area_el)
            self._auto_layout_children(children)
            origin = QPointF(running_x + PAD, AREA_TOP + HEADER)
            self._area_origin[area_el.id] = origin

            tlevel = self.tile_level()
            for child in children:
                node = TileNode(child, tlevel, self)
                node.area_id = area_el.id
                node.area_origin = origin
                self._scene.addItem(node)
                node.setPos(origin.x() + child.pos_x, origin.y() + child.pos_y)
                self._nodes[child.id] = node

            rect = self._area_bounds(area_el.id)
            self._area_rects[area_el.id] = rect

            area_item = ContainerArea(area_el, rect, element_color(area_el),
                                      active=(area_el.id == self.active_area_id))
            self._scene.addItem(area_item)
            self._areas[area_el.id] = area_item

            for child in children:
                for conn in getattr(child, "connections", []):
                    if child.id in self._nodes and conn.target_id in self._nodes:
                        item = ConnectionItem(self._nodes[child.id],
                                              self._nodes[conn.target_id], conn.kind)
                        self._scene.addItem(item)
                        self._connections.append(item)

            running_x = rect.right() + AREA_GAP

        self._refresh_connections()
        self._apply_scale()
        self._update_scene_rect_from_areas()
        self._apply_pending_focus()
        self.level_changed.emit(self.area_level())
        self.zoom_changed.emit(self.current_percent())

    def _auto_layout_children(self, children: List) -> None:
        slot = 0.0
        for c in children:
            if c.pos_x == 0.0 and c.pos_y == 0.0:
                c.pos_x = slot
                c.pos_y = 0.0
            slot = max(slot, c.pos_x) + nodes.TILE_W + TILE_GAP

    def _refresh_connections(self) -> None:
        node_list = list(self._nodes.values())
        for conn in self._connections:
            conn.set_obstacles(node_list)
            conn.update_path()

    def _update_scene_rect_from_areas(self) -> None:
        margin = 1400.0
        vmargin = 420.0
        rect: Optional[QRectF] = None
        for r in self._area_rects.values():
            rect = QRectF(r) if rect is None else rect.united(r)
        if rect is None:
            rect = QRectF(0.0, AREA_TOP, _area_min_w(), AREA_H)
        self._scene.setSceneRect(rect.adjusted(-margin, -vmargin, margin, vmargin))

    def _apply_scale(self) -> None:
        self.resetTransform()
        self.scale(self.tile_scale, self.tile_scale)

    def _area_bounds(self, area_id: str) -> QRectF:
        """Габариты области по фактическим позициям плиток (растёт во все стороны)."""
        origin = self._area_origin.get(area_id, QPointF(0.0, 0.0))
        area_el = self.plan.get(area_id)
        children = get_children(area_el) if area_el else []
        tw, th = nodes.TILE_W, nodes.TILE_H
        if children:
            min_x = min(c.pos_x for c in children)
            max_x = max(c.pos_x + tw for c in children)
            min_y = min(c.pos_y for c in children)
            max_y = max(c.pos_y + th for c in children)
        else:
            min_x, max_x, min_y, max_y = 0.0, tw, 0.0, th
        left = origin.x() + min(0.0, min_x) - PAD
        right = origin.x() + max(tw, max_x) + PAD
        top = origin.y() + min(0.0, min_y) - HEADER
        bottom = origin.y() + max(th, max_y) + PAD
        width = max(_area_min_w(), right - left)
        return QRectF(left, top, width, bottom - top)

    # ──────────────────────────────────────────────────────────────────
    # Точечная сетка / тема
    # ──────────────────────────────────────────────────────────────────
    def set_theme(self, name: str) -> None:
        theme = THEMES.get(name, THEMES["dark"])
        self._bg_color = QColor(theme["bg"])
        self._grid_color = QColor(*theme["grid"])
        self.setBackgroundBrush(QBrush(self._bg_color))
        self.viewport().update()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._bg_color)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._grid_color)
        left = rect.left() - (rect.left() % GRID)
        top = rect.top() - (rect.top() % GRID)
        y = top
        while y < rect.bottom():
            x = left
            while x < rect.right():
                painter.drawEllipse(QPointF(x, y), 1.6, 1.6)
                x += GRID
            y += GRID

    # ──────────────────────────────────────────────────────────────────
    # Привязка и ограничение плиток областью
    # ──────────────────────────────────────────────────────────────────
    def snap_scene_point(self, p: QPointF) -> QPointF:
        if not self.snap_enabled:
            return p
        gx = round(p.x() / GRID) * GRID
        gy = round(p.y() / GRID) * GRID
        if abs(gx - p.x()) <= SNAP_RADIUS and abs(gy - p.y()) <= SNAP_RADIUS:
            return QPointF(gx, gy)
        return p

    def constrain_tile_point(self, node: TileNode, p: QPointF) -> QPointF:
        origin = node.area_origin
        local_x = max(0.0, p.x() - origin.x())
        local_y = p.y() - origin.y()
        snapped = self.snap_scene_point(QPointF(origin.x() + local_x,
                                                origin.y() + local_y))
        lx = max(0.0, snapped.x() - origin.x())
        ly = snapped.y() - origin.y()
        return QPointF(origin.x() + lx, origin.y() + ly)

    def set_snap(self, enabled: bool) -> None:
        self.snap_enabled = enabled

    def on_node_moved(self, node: TileNode) -> None:
        if self._relaying:
            return
        origin = node.area_origin
        node.element.pos_x = node.pos().x() - origin.x()
        node.element.pos_y = node.pos().y() - origin.y()
        self._drag_dirty = True
        self._refresh_connections()
        area = self._areas.get(node.area_id)
        if area is not None:
            area.set_rect(self._area_bounds(node.area_id))

    def on_tile_released(self, node: TileNode) -> None:
        if not self._drag_dirty:
            return
        self._drag_dirty = False
        moved = self._selected_tiles() or [node]
        self._resolve_overlap_multi(moved)
        self._relayout_areas()
        self.commit_state()
        self.notify_plan_changed()

    # ──────────────────────────────────────────────────────────────────
    # Перекладка областей без пересборки сцены (сохраняет выделение)
    # ──────────────────────────────────────────────────────────────────
    def _relayout_areas(self) -> None:
        self._relaying = True
        try:
            running_x = 0.0
            for area_el in self._areas_list():
                if area_el.id not in self._areas:
                    continue
                origin = QPointF(running_x + PAD, AREA_TOP + HEADER)
                self._area_origin[area_el.id] = origin
                for child in get_children(area_el):
                    n = self._nodes.get(child.id)
                    if n is not None:
                        n.area_origin = origin
                        n.setPos(origin.x() + child.pos_x, origin.y() + child.pos_y)
                rect = self._area_bounds(area_el.id)
                self._area_rects[area_el.id] = rect
                self._areas[area_el.id].set_rect(rect)
                running_x = rect.right() + AREA_GAP
        finally:
            self._relaying = False
        self._refresh_connections()
        self._update_scene_rect_from_areas()

    # ──────────────────────────────────────────────────────────────────
    # Запрет наложения плиток
    # ──────────────────────────────────────────────────────────────────
    def _resolve_overlap(self, node: TileNode) -> None:
        self._resolve_overlap_multi([node])

    def _resolve_overlap_multi(self, moved: List[TileNode]) -> None:
        by_area: Dict[str, List[TileNode]] = {}
        for n in moved:
            if isinstance(n, TileNode):
                by_area.setdefault(n.area_id, []).append(n)

        for area_id, group in by_area.items():
            others = [n for n in self._nodes.values()
                      if n.area_id == area_id and n not in group]
            occupied: List[Tuple[float, float]] = [
                (n.element.pos_x, n.element.pos_y) for n in others
            ]
            group.sort(key=lambda n: (n.element.pos_y, n.element.pos_x))
            for n in group:
                fx, fy = find_free_slot(n.element.pos_x, n.element.pos_y, occupied,
                                        nodes.TILE_W, nodes.TILE_H, GRID)
                n.element.pos_x, n.element.pos_y = fx, fy
                occupied.append((fx, fy))
                origin = n.area_origin
                self._relaying = True
                try:
                    n.setPos(origin.x() + fx, origin.y() + fy)
                finally:
                    self._relaying = False

    # ──────────────────────────────────────────────────────────────────
    # История (undo / redo)
    # ──────────────────────────────────────────────────────────────────
    def _reset_history(self) -> None:
        self._history = [self.plan.to_dict()]
        self._hist_index = 0
        self._coalesce_key = None
        self.history_changed.emit()

    def commit_state(self, coalesce_key=None) -> None:
        snap = self.plan.to_dict()
        if (coalesce_key is not None and coalesce_key == self._coalesce_key
                and self._hist_index == len(self._history) - 1
                and self._hist_index >= 0):
            self._history[self._hist_index] = snap
            return
        del self._history[self._hist_index + 1:]
        self._history.append(snap)
        if len(self._history) > HISTORY_LIMIT:
            self._history.pop(0)
        self._hist_index = len(self._history) - 1
        self._coalesce_key = coalesce_key
        self.history_changed.emit()

    def can_undo(self) -> bool:
        return self._hist_index > 0

    def can_redo(self) -> bool:
        return self._hist_index < len(self._history) - 1

    def undo(self) -> None:
        if not self.can_undo():
            return
        self._hist_index -= 1
        self._load_state(self._history[self._hist_index])

    def redo(self) -> None:
        if not self.can_redo():
            return
        self._hist_index += 1
        self._load_state(self._history[self._hist_index])

    def _load_state(self, snap: dict) -> None:
        self._coalesce_key = None
        self.plan = TrainingPlan.from_dict(snap)
        if self.scope_id is not None and self.plan.get(self.scope_id) is None:
            self.scope_id = None
            self.active_area_id = None
        self._focus_requested = False
        self._render()
        self.node_deselected.emit()
        self.history_changed.emit()
        self.notify_plan_changed()

    # ──────────────────────────────────────────────────────────────────
    # Буфер обмена: копировать / вставить / дублировать
    # ──────────────────────────────────────────────────────────────────
    def copy_selection(self) -> None:
        tiles = self._selected_tiles()
        if not tiles:
            return
        self._clipboard = [clone_element(t.element) for t in tiles]
        self._clipboard_level = self.tile_level().value

    def duplicate_selection(self) -> None:
        tiles = self._selected_tiles()
        if not tiles:
            return
        self._clipboard = [clone_element(t.element) for t in tiles]
        self._clipboard_level = self.tile_level().value
        self.paste()

    def paste(self, scene_pos: Optional[QPointF] = None) -> None:
        if not self._clipboard or self._clipboard_level != self.tile_level().value:
            return
        areas = self._areas_list()
        area_id = self.active_area_id or (areas[0].id if areas else None)
        if area_id is None or self.plan.get(area_id) is None:
            return

        new_ids: List[str] = []
        for src in self._clipboard:
            clone = clone_element(src)
            clone.pos_x = max(0.0, src.pos_x + GRID)
            clone.pos_y = max(0.0, src.pos_y + GRID)
            if self.plan.add_child(area_id, clone):
                new_ids.append(clone.id)
        if not new_ids:
            return

        self.active_area_id = area_id
        self._render()
        pasted = [self._nodes[i] for i in new_ids if i in self._nodes]
        self._resolve_overlap_multi(pasted)
        self._relayout_areas()
        self._scene.clearSelection()
        for n in pasted:
            n.setSelected(True)
        self.commit_state()
        self.notify_plan_changed()

    def select_all_tiles(self) -> None:
        self._scene.clearSelection()
        for n in self._nodes.values():
            n.setSelected(True)

    # ──────────────────────────────────────────────────────────────────
    # Авто-расстановка
    # ──────────────────────────────────────────────────────────────────
    def auto_layout(self) -> None:
        changed = False
        for area_el in self._areas_list():
            children = get_children(area_el)
            if children:
                self._grid_arrange(children)
                changed = True
        if not changed:
            return
        self._relayout_areas()
        self.commit_state()
        self.notify_plan_changed()

    def _grid_arrange(self, children: List) -> None:
        ordered = sorted(children, key=lambda c: (c.pos_y, c.pos_x))
        per_row = 6
        step_x = nodes.TILE_W + TILE_GAP
        step_y = nodes.TILE_H + TILE_GAP
        for i, c in enumerate(ordered):
            c.pos_x = (i % per_row) * step_x
            c.pos_y = (i // per_row) * step_y

    # ──────────────────────────────────────────────────────────────────
    # Размер плиток
    # ──────────────────────────────────────────────────────────────────
    def apply_tile_size(self, width: float, height: float) -> None:
        nodes.set_tile_size(width, height)
        self._render()

    # ──────────────────────────────────────────────────────────────────
    # Связи
    # ──────────────────────────────────────────────────────────────────
    def _set_source(self, node: Optional[TileNode]) -> None:
        if self._source_node is not None:
            self._source_node.set_connection_source(False)
        self._source_node = node
        if node is not None:
            node.set_connection_source(True)

    def _connect_to(self, target: TileNode) -> None:
        source = self._source_node
        if source is None or source is target:
            self._set_source(None)
            return
        if self.plan.add_connection(source.element.id, target.element.id):
            item = ConnectionItem(source, target, "sequence")
            item.set_obstacles(list(self._nodes.values()))
            self._scene.addItem(item)
            self._connections.append(item)
            self.commit_state()
            self.notify_plan_changed()
        self._set_source(None)

    # ──────────────────────────────────────────────────────────────────
    # Навигация
    # ──────────────────────────────────────────────────────────────────
    def enter_scope(self, area_id: str) -> bool:
        if self.tile_level().value <= MIN_TILE_LEVEL:
            return False
        if self.plan.get(area_id) is None:
            return False
        self._capture_focus()
        self.scope_id = area_id
        remembered = self._scope_focus.get(area_id)
        self.active_area_id = remembered
        self.tile_scale = SCALE_MAX
        self._focus_zoom_in = True
        self._request_focus(remembered)
        self._render()
        return True

    def enter_deeper(self) -> bool:
        if self.tile_level().value <= MIN_TILE_LEVEL:
            return False
        area_id = self._area_under_center()
        if area_id is None:
            areas = self._areas_list()
            area_id = areas[0].id if areas else None
        if area_id is None:
            return False
        return self.enter_scope(area_id)

    def go_up(self) -> bool:
        if self.scope_id is None:
            return False
        self._capture_focus()
        leaving = self.scope_id
        self.scope_id = self.plan.parent_id(self.scope_id)
        self.active_area_id = leaving
        self.tile_scale = SCALE_MAX
        self._scope_focus[self.scope_id] = leaving
        self._focus_zoom_in = False
        self._request_focus(leaving)
        self._render()
        return True

    # ── память положения камеры между уровнями ──
    def _capture_focus(self) -> None:
        aid = self._area_under_center()
        if aid is not None:
            self._scope_focus[self.scope_id] = aid

    def _request_focus(self, element_id: Optional[str]) -> None:
        self._pending_focus_id = element_id
        self._focus_requested = True

    def _apply_pending_focus(self) -> None:
        if not self._focus_requested:
            return
        self._focus_requested = False
        fid = self._pending_focus_id
        self._pending_focus_id = None
        if fid is None:
            fid = self.active_area_id
        if fid is None:
            return
        if fid in self._area_rects:
            target = self._area_rects[fid].center()
        elif fid in self._nodes:
            target = self._nodes[fid].center_scene()
        else:
            return
        self._move_camera_to(target, self._focus_zoom_in)

    def _move_camera_to(self, target: QPointF, zoom_in: bool) -> None:
        if not self.animations_enabled:
            self.centerOn(target)
            return
        self._stop_camera_anim()
        start_center = self.mapToScene(self.viewport().rect().center())
        target_scale = self.tile_scale
        start_scale = target_scale * (0.82 if zoom_in else 1.2)

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(280)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def on_value(value) -> None:
            t = float(value)
            s = start_scale + (target_scale - start_scale) * t
            self.resetTransform()
            self.scale(s, s)
            cx = start_center.x() + (target.x() - start_center.x()) * t
            cy = start_center.y() + (target.y() - start_center.y()) * t
            self.centerOn(cx, cy)

        def on_finished() -> None:
            self.resetTransform()
            self.scale(target_scale, target_scale)
            self.centerOn(target)

        anim.valueChanged.connect(on_value)
        anim.finished.connect(on_finished)
        self._cam_anim = anim
        anim.start()

    def _stop_camera_anim(self) -> None:
        if self._cam_anim is not None:
            self._cam_anim.stop()
            self._cam_anim = None

    def _navigate_to_tile_level(self, level: HierarchyLevel) -> None:
        guard = 0
        while self.tile_level().value < level.value and guard < 12:
            if not self.go_up():
                break
            guard += 1
        guard = 0
        while self.tile_level().value > level.value and guard < 12:
            if not self.enter_deeper():
                break
            guard += 1

    def go_to_tile_level(self, level_value: int) -> None:
        level_value = max(MIN_TILE_LEVEL, min(MAX_TILE_LEVEL, level_value))
        self._navigate_to_tile_level(HierarchyLevel(level_value))
        self.tile_scale = SCALE_MAX
        self._apply_scale()
        self.zoom_changed.emit(self.current_percent())

    def _area_under_center(self) -> Optional[str]:
        center = self.mapToScene(self.viewport().rect().center())
        for area_id, rect in self._area_rects.items():
            if rect.contains(center):
                return area_id
        best, best_d = None, None
        for area_id, rect in self._area_rects.items():
            d = (rect.center() - center)
            dist = d.x() * d.x() + d.y() * d.y()
            if best_d is None or dist < best_d:
                best_d, best = dist, area_id
        return best

    # ──────────────────────────────────────────────────────────────────
    # Масштаб
    # ──────────────────────────────────────────────────────────────────
    def current_percent(self) -> int:
        top = 200 - (self.tile_level().value - 1) * 30
        t = (SCALE_MAX - self.tile_scale) / (SCALE_MAX - SCALE_MIN)
        return int(round(top - t * 30))

    def set_percent(self, percent: int) -> None:
        percent = max(50, min(200, percent))
        target = max(MIN_TILE_LEVEL, min(MAX_TILE_LEVEL, 1 + (200 - percent) // 30))
        self._navigate_to_tile_level(HierarchyLevel(target))
        top = 200 - (self.tile_level().value - 1) * 30
        t = max(0.0, min(1.0, (top - percent) / 30.0))
        self.tile_scale = SCALE_MAX - t * (SCALE_MAX - SCALE_MIN)
        self._apply_scale()
        self.zoom_changed.emit(self.current_percent())

    def _zoom(self, zoom_in: bool) -> None:
        factor = 1.15 if zoom_in else 1.0 / 1.15
        new_scale = self.tile_scale * factor
        if zoom_in and new_scale > SCALE_MAX + 1e-6:
            if not self.enter_deeper():
                self.tile_scale = SCALE_MAX
                self._apply_scale()
        elif not zoom_in and new_scale < SCALE_MIN - 1e-6:
            if not self.go_up():
                self.tile_scale = SCALE_MIN
                self._apply_scale()
        else:
            self.tile_scale = max(SCALE_MIN, min(SCALE_MAX, new_scale))
            self._apply_scale()
        self.zoom_changed.emit(self.current_percent())

    # ──────────────────────────────────────────────────────────────────
    # Создание / удаление
    # ──────────────────────────────────────────────────────────────────
    def create_tile(self, element, area_id: Optional[str] = None,
                    scene_pos: Optional[QPointF] = None) -> None:
        area_id = area_id or self.active_area_id
        areas = self._areas_list()
        if area_id is None and areas:
            area_id = areas[0].id
        if area_id is None:
            return
        area_el = self.plan.get(area_id)
        if area_el is None:
            return
        children = get_children(area_el)
        if scene_pos is not None and area_id in self._area_origin:
            origin = self._area_origin[area_id]
            element.pos_x = max(0.0, scene_pos.x() - origin.x())
            element.pos_y = max(0.0, scene_pos.y() - origin.y())
        else:
            element.pos_x = (max((c.pos_x for c in children),
                                 default=-(nodes.TILE_W + TILE_GAP))
                             + nodes.TILE_W + TILE_GAP) if children else 0.0
            element.pos_y = 0.0
        if self.plan.add_child(area_id, element):
            self.active_area_id = area_id
            self._render()
            node = self._nodes.get(element.id)
            if node is not None:
                self._resolve_overlap(node)
                self._relayout_areas()
            self.commit_state()
            self.notify_plan_changed()

    def create_area(self) -> bool:
        if self.scope_id is None:
            return False
        new = make_element(self.area_level())
        if self.plan.add_child(self.scope_id, new):
            self.active_area_id = new.id
            self._render()
            self.commit_state()
            self.notify_plan_changed()
            return True
        return False

    def delete_selected(self) -> None:
        conns = [i for i in self._scene.selectedItems()
                 if isinstance(i, ConnectionItem)]
        tiles = self._selected_tiles()
        if not conns and not tiles:
            return
        for c in conns:
            self.plan.remove_connection(c.source.element.id, c.target.element.id)
        for t in tiles:
            self.plan.remove(t.element.id)
        self.node_deselected.emit()
        self._render()
        self.commit_state()
        self.notify_plan_changed()

    def get_selected_element(self):
        node = self._selected_node()
        return node.element if node else None

    def refresh_selected_node(self) -> None:
        node = self._selected_node()
        if node:
            node.update()
        for area in self._areas.values():
            area.update()

    def notify_plan_changed(self) -> None:
        self.plan_changed.emit()

    # ──────────────────────────────────────────────────────────────────
    # Экспорт изображения / PDF
    # ──────────────────────────────────────────────────────────────────
    def _export_rect(self) -> QRectF:
        rect = self._scene.itemsBoundingRect()
        if rect.isNull():
            rect = QRectF(0.0, AREA_TOP, _area_min_w(), AREA_H)
        return rect.adjusted(-40, -40, 40, 40)

    def export_image(self, path: str) -> None:
        self._scene.clearSelection()
        rect = self._export_rect()
        scale = 2.0
        image = QImage(max(1, int(rect.width() * scale)),
                       max(1, int(rect.height() * scale)),
                       QImage.Format.Format_ARGB32)
        image.fill(self._bg_color)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        image.save(path)

    def export_pdf(self, path: str) -> None:
        from PyQt6.QtGui import QPageSize, QPdfWriter
        from PyQt6.QtCore import QSizeF, QMarginsF

        self._scene.clearSelection()
        rect = self._export_rect()
        writer = QPdfWriter(path)
        writer.setResolution(150)
        page = QPageSize(QSizeF(rect.width(), rect.height()), QPageSize.Unit.Point,
                         "plan", QPageSize.SizeMatchPolicy.ExactMatch)
        writer.setPageSize(page)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0))
        painter = QPainter(writer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._scene.render(painter, QRectF(painter.viewport()), rect)
        painter.end()

    # ──────────────────────────────────────────────────────────────────
    # Выбор / активная область
    # ──────────────────────────────────────────────────────────────────
    def _selected_node(self) -> Optional[TileNode]:
        for item in self._scene.selectedItems():
            if isinstance(item, TileNode):
                return item
        return None

    def _selected_tiles(self) -> List[TileNode]:
        return [i for i in self._scene.selectedItems() if isinstance(i, TileNode)]

    def _set_active_area(self, area_id: Optional[str]) -> None:
        self.active_area_id = area_id
        for aid, area in self._areas.items():
            area.set_active(aid == area_id)

    def _node_at(self, view_pos) -> Optional[TileNode]:
        item = self.itemAt(view_pos)
        while item is not None:
            if isinstance(item, TileNode):
                return item
            item = item.parentItem()
        return None

    def _area_at(self, view_pos) -> Optional[ContainerArea]:
        for item in self.items(view_pos):
            if isinstance(item, ContainerArea):
                return item
        return None

    def _on_selection_changed(self) -> None:
        node = self._selected_node()
        if node is not None:
            self.node_selected.emit(node.element)
            self._set_active_area(node.area_id)
        else:
            self.node_deselected.emit()

    # ──────────────────────────────────────────────────────────────────
    # События
    # ──────────────────────────────────────────────────────────────────
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._zoom(event.angleDelta().y() > 0)
            event.accept()
            return
        delta = event.angleDelta().y() or event.angleDelta().x()
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - int(delta * 0.6))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_last = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._lmb_press = event.position()
            self._lmb_moved = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return
        if (event.buttons() & Qt.MouseButton.LeftButton) and not self._lmb_moved:
            if (event.position() - self._lmb_press).manhattanLength() > 4:
                self._lmb_moved = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            if not self._lmb_moved:
                pos = event.position().toPoint()
                if self._node_at(pos) is None and not self._scene.selectedItems():
                    area = self._area_at(pos)
                    if area is not None:
                        self._set_active_area(area.element.id)
                        self.node_selected.emit(area.element)
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        pos = event.position().toPoint()
        node = self._node_at(pos)
        if node is not None:
            self.enter_scope(node.area_id)
            event.accept()
            return
        area = self._area_at(pos)
        if area is not None:
            self.enter_scope(area.element.id)
            event.accept()
            return
        self.create_area()
        event.accept()

    def contextMenuEvent(self, event):
        pos = event.pos()
        node = self._node_at(pos)
        menu = QMenu(self)
        if node is not None:
            if not node.isSelected():
                self._scene.clearSelection()
                node.setSelected(True)
            element = node.element
            menu.addAction("Свойства",
                           lambda: self.node_selected.emit(element))
            menu.addAction("Дублировать  (Ctrl+D)", self.duplicate_selection)
            menu.addAction("Копировать  (Ctrl+C)", self.copy_selection)
            menu.addAction("Сохранить в библиотеку",
                           lambda: self.save_to_library_requested.emit(element))
            menu.addSeparator()
            if self._source_node is None:
                menu.addAction("Создать связь отсюда",
                               lambda: self._set_source(node))
            elif self._source_node is node:
                menu.addAction("Отменить связь", lambda: self._set_source(None))
            else:
                menu.addAction("Связать сюда", lambda: self._connect_to(node))
            menu.addSeparator()
            menu.addAction("Удалить  (Del)", self.delete_selected)
        else:
            scene_pos = self.mapToScene(pos)
            if self._clipboard and self._clipboard_level == self.tile_level().value:
                menu.addAction("Вставить  (Ctrl+V)",
                               lambda: self.paste(scene_pos))
            if self.scope_id is not None:
                menu.addAction("Добавить область", self.create_area)
            menu.addAction("Авто-расстановка  (Ctrl+L)", self.auto_layout)
            menu.addAction("Выделить всё  (Ctrl+A)", self.select_all_tiles)
        menu.exec(event.globalPos())
        event.accept()

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if ctrl and key == Qt.Key.Key_Z and not shift:
            self.undo(); event.accept(); return
        if (ctrl and key == Qt.Key.Key_Y) or (ctrl and shift and key == Qt.Key.Key_Z):
            self.redo(); event.accept(); return
        if ctrl and key == Qt.Key.Key_C:
            self.copy_selection(); event.accept(); return
        if ctrl and key == Qt.Key.Key_V:
            self.paste(); event.accept(); return
        if ctrl and key == Qt.Key.Key_D:
            self.duplicate_selection(); event.accept(); return
        if ctrl and key == Qt.Key.Key_A:
            self.select_all_tiles(); event.accept(); return
        if ctrl and key == Qt.Key.Key_L:
            self.auto_layout(); event.accept(); return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected(); event.accept(); return
        if key == Qt.Key.Key_Escape:
            self._set_source(None); event.accept(); return
        super().keyPressEvent(event)

    # ──────────────────────────────────────────────────────────────────
    # Drag & drop из библиотеки
    # ──────────────────────────────────────────────────────────────────
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        element = self._element_from_mime(event.mimeData().text())
        if element is None:
            return
        view_pos = event.position().toPoint()
        scene_pos = self.mapToScene(view_pos)
        target = QPointF(scene_pos.x() - nodes.TILE_W / 2,
                         scene_pos.y() - nodes.TILE_H / 2)
        area = self._area_at(view_pos)
        area_id = area.element.id if area is not None else None
        self.create_tile(element, area_id=area_id, scene_pos=target)
        event.acceptProposedAction()

    def _element_from_mime(self, text: str):
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        tlevel = self.tile_level()
        if HierarchyLevel(data.get("level", tlevel.value)) != tlevel:
            return None
        if data.get("kind") == "template" and data.get("entry"):
            from core.library_store import build_element
            return build_element(data["entry"])
        return make_element(tlevel, data.get("title"))
