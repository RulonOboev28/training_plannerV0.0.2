"""Диалог журнала действий с откатом к выбранному шагу."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)

from core.action_journal import format_entry

if TYPE_CHECKING:
    from ui.canvas.viewport import CanvasView


class HistoryDialog(QDialog):
    def __init__(self, canvas: CanvasView, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self.setWindowTitle("История изменений")
        self.setMinimumSize(560, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Последние 25 действий. Дата — привязка к календарю плана.\n"
            "Откат уберёт выбранное действие и все более новые."))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        self.btn_rollback = QPushButton("Откатить до выбранного (включая его)")
        self.btn_rollback.setObjectName("accent")
        self.btn_rollback.clicked.connect(self._rollback)
        row.addWidget(self.btn_rollback)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._reload_list()

    def _reload_list(self) -> None:
        self.list_widget.clear()
        entries = self._canvas.action_journal.entries()
        for entry in reversed(entries):
            item = QListWidgetItem(format_entry(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry.hist_index)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _rollback(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        hist_index = item.data(Qt.ItemDataRole.UserRole)
        if hist_index is None:
            return
        text = item.text()
        answer = QMessageBox.question(
            self,
            "Откат",
            f"Откатить план к состоянию до этого действия?\n\n{text}\n\n"
            "Будут отменены это действие и все более новые.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self._canvas.rollback_before(int(hist_index)):
            QMessageBox.warning(
                self, "Откат", "Не удалось выполнить откат для этого шага.")
            return
        self.accept()
