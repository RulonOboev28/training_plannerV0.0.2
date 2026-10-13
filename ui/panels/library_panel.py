"""Левая панель: библиотека компонентов и пользовательские коллекции."""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QDrag, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from core import library_store
from core.models import HierarchyLevel, LEVEL_ITEM_NAMES, LEVEL_NAMES, make_element

MIME_TEMPLATE = "application/x-training-template"


def _preset_entries(_level: HierarchyLevel) -> List[Dict]:
    return []


class _PresetList(QListWidget):
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


class _CollectionTree(QTreeWidget):
    ROLE_KIND = Qt.ItemDataRole.UserRole
    ROLE_COL_ID = Qt.ItemDataRole.UserRole + 1
    ROLE_ENTRY_ID = Qt.ItemDataRole.UserRole + 2
    ROLE_ENTRY = Qt.ItemDataRole.UserRole + 3

    def __init__(self, panel: "LibraryPanel"):
        super().__init__()
        self._panel = panel
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAnimated(True)
        self.setIndentation(16)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def _context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        menu = QMenu(self)
        if item is None:
            act = menu.addAction("Новая коллекция…")
            act.triggered.connect(self._panel._create_collection)
        elif item.parent() is None:
            menu.addAction("Переименовать…", lambda: self._panel._rename_collection(item))
            menu.addAction("Удалить коллекцию", lambda: self._panel._delete_collection(item))
        else:
            menu.addAction("Удалить шаблон", lambda: self._panel._delete_entry(item))
        menu.exec(self.viewport().mapToGlobal(pos))

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item is None or item.parent() is None:
            return
        payload = self._template_payload(item)
        if payload is None:
            return
        mime = QMimeData()
        mime.setText(json.dumps(payload, ensure_ascii=False))
        mime.setData(MIME_TEMPLATE, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return
        dst = self.itemAt(event.position().toPoint())
        dragged = self.currentItem()
        if dragged is None or dragged.parent() is None:
            event.ignore()
            return

        src_col = dragged.parent().data(0, self.ROLE_COL_ID)
        entry_id = dragged.data(0, self.ROLE_ENTRY_ID)
        from_index = dragged.parent().indexOfChild(dragged)

        if dst is None:
            event.ignore()
            return

        if dst.parent() is None:
            to_col = dst.data(0, self.ROLE_COL_ID)
            to_index = dst.childCount()
        else:
            to_col = dst.parent().data(0, self.ROLE_COL_ID)
            to_index = dst.parent().indexOfChild(dst)
            if self.dropIndicatorPosition() in (
                    QAbstractItemView.DropIndicatorPosition.OnItem,
                    QAbstractItemView.DropIndicatorPosition.BelowItem):
                to_index += 1

        if src_col == to_col and from_index < to_index:
            to_index -= 1

        if library_store.move_entry(src_col, entry_id, to_col, to_index):
            self._panel.refresh_personal()
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _template_payload(item: QTreeWidgetItem) -> Optional[Dict]:
        entry = item.data(0, _CollectionTree.ROLE_ENTRY)
        if not entry:
            return None
        return {
            "kind": "template",
            "level": entry["level"],
            "title": entry.get("title", ""),
            "entry": entry,
        }


class LibraryPanel(QFrame):
    request_add = pyqtSignal(object)

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
        self.tree = _CollectionTree(self)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)
        self.tab_presets = _PresetList()
        self.tab_presets.itemDoubleClicked.connect(self._on_preset_double_click)
        self.tabs.addTab(self.tree, "Мои коллекции")
        self.tabs.addTab(self.tab_presets, "Пресеты")
        root.addWidget(self.tabs, 1)

        self.btn_add_empty = QPushButton("＋  Пустой элемент")
        self.btn_add_empty.setObjectName("accent")
        self.btn_add_empty.clicked.connect(self._add_empty)
        root.addWidget(self.btn_add_empty)

        self.btn_new_collection = QPushButton("＋  Новая коллекция")
        self.btn_new_collection.clicked.connect(self._create_collection)
        root.addWidget(self.btn_new_collection)

        row = QHBoxLayout()
        self.btn_export = QPushButton("Экспорт")
        self.btn_import = QPushButton("Импорт")
        self.btn_export.clicked.connect(self._export)
        self.btn_import.clicked.connect(self._import)
        row.addWidget(self.btn_export)
        row.addWidget(self.btn_import)
        root.addLayout(row)

        self.set_level(self.level)

    def set_level(self, level: HierarchyLevel) -> None:
        self.level = level
        self.level_badge.setText(f"Уровень: {LEVEL_NAMES.get(level, '')}")
        item_name = LEVEL_ITEM_NAMES.get(level, "элемент")
        self.btn_add_empty.setText(f"＋  Пустой: {item_name}")
        self._reload()

    def refresh_personal(self) -> None:
        self.tree.clear()
        cols = library_store.list_collections()
        if not cols:
            placeholder = QTreeWidgetItem(["Создайте коллекцию для шаблонов"])
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tree.addTopLevelItem(placeholder)
            return
        for col in cols:
            entries = [e for e in col.get("entries", [])
                       if e.get("level") == self.level.value]
            head = QTreeWidgetItem([col["title"]])
            head.setData(0, _CollectionTree.ROLE_KIND, "collection")
            head.setData(0, _CollectionTree.ROLE_COL_ID, col["id"])
            head.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Bold))
            head.setExpanded(True)
            head.setFlags(head.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            self.tree.addTopLevelItem(head)
            for entry in entries:
                child = QTreeWidgetItem([entry.get("title", "Без названия")])
                child.setData(0, _CollectionTree.ROLE_KIND, "entry")
                child.setData(0, _CollectionTree.ROLE_COL_ID, col["id"])
                child.setData(0, _CollectionTree.ROLE_ENTRY_ID, entry.get("id"))
                child.setData(0, _CollectionTree.ROLE_ENTRY, entry)
                child.setFont(0, QFont("Segoe UI", 10))
                child.setFlags(
                    child.flags()
                    | Qt.ItemFlag.ItemIsDragEnabled
                    | Qt.ItemFlag.ItemIsDropEnabled)
                head.addChild(child)

    def _reload(self) -> None:
        self._fill_presets(_preset_entries(self.level))
        self.refresh_personal()

    def _fill_presets(self, entries: List[Dict]) -> None:
        self.tab_presets.clear()
        if not entries:
            placeholder = QListWidgetItem("Пресеты отключены")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tab_presets.addItem(placeholder)
            return
        for entry in entries:
            data = {"kind": "template", "level": entry["level"],
                    "title": entry.get("title", ""), "entry": entry}
            item = QListWidgetItem(entry.get("title", "Без названия"))
            item.setFont(QFont("Segoe UI", 11))
            item.setData(Qt.ItemDataRole.UserRole, data)
            self.tab_presets.addItem(item)

    def _filter(self, text: str) -> None:
        text = text.lower()
        widget = self.tabs.currentWidget()
        if widget is self.tree:
            for i in range(self.tree.topLevelItemCount()):
                head = self.tree.topLevelItem(i)
                any_visible = False
                for j in range(head.childCount()):
                    child = head.child(j)
                    vis = text in child.text(0).lower() or text in head.text(0).lower()
                    child.setHidden(not vis)
                    any_visible = any_visible or vis
                head.setHidden(not any_visible and text not in head.text(0).lower())
        elif isinstance(widget, QListWidget):
            for i in range(widget.count()):
                it = widget.item(i)
                it.setHidden(text not in it.text().lower())

    def _on_tree_double_click(self, item: QTreeWidgetItem, _col: int) -> None:
        if item.parent() is None:
            item.setExpanded(not item.isExpanded())
            return
        payload = _CollectionTree._template_payload(item)
        if payload:
            self.request_add.emit(library_store.build_element(payload["entry"]))

    def _on_preset_double_click(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.request_add.emit(library_store.build_element(data["entry"]))

    def _add_empty(self) -> None:
        self.request_add.emit(make_element(self.level))

    def _create_collection(self) -> None:
        name, ok = QInputDialog.getText(self, "Новая коллекция", "Название:")
        if ok and name.strip():
            library_store.create_collection(name.strip())
            self.refresh_personal()

    def _rename_collection(self, item: QTreeWidgetItem) -> None:
        cid = item.data(0, _CollectionTree.ROLE_COL_ID)
        name, ok = QInputDialog.getText(self, "Переименовать", "Название:", text=item.text(0))
        if ok and name.strip():
            library_store.rename_collection(cid, name.strip())
            self.refresh_personal()

    def _delete_collection(self, item: QTreeWidgetItem) -> None:
        cid = item.data(0, _CollectionTree.ROLE_COL_ID)
        if QMessageBox.question(
                self, "Удалить коллекцию",
                f"Удалить «{item.text(0)}» и все шаблоны внутри?",
        ) != QMessageBox.StandardButton.Yes:
            return
        library_store.delete_collection(cid)
        self.refresh_personal()

    def _delete_entry(self, item: QTreeWidgetItem) -> None:
        cid = item.data(0, _CollectionTree.ROLE_COL_ID)
        eid = item.data(0, _CollectionTree.ROLE_ENTRY_ID)
        library_store.remove_entry(cid, eid)
        self.refresh_personal()

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
                QMessageBox.information(self, "Импорт", f"Добавлено шаблонов: {count}")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Ошибка", f"Не удалось импортировать: {exc}")
