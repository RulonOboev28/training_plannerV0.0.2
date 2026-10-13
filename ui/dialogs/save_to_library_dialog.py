"""Выбор коллекции при сохранении шаблона в библиотеку."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QInputDialog, QLabel,
    QLineEdit, QVBoxLayout,
)

from core import library_store


class SaveToLibraryDialog(QDialog):
    def __init__(self, element_title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сохранить в библиотеку")
        self._collection_id: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Шаблон: {element_title}"))

        form = QFormLayout()
        self.collection_combo = QComboBox()
        self._reload_collections()
        form.addRow("Коллекция:", self.collection_combo)
        self.new_collection = QLineEdit()
        self.new_collection.setPlaceholderText("Или введите название новой коллекции")
        form.addRow("Новая:", self.new_collection)
        layout.addLayout(form)

        btn_new = QDialogButtonBox()
        create_btn = btn_new.addButton("Создать коллекцию…", QDialogButtonBox.ButtonRole.ActionRole)
        create_btn.clicked.connect(self._create_collection)
        layout.addWidget(btn_new)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _reload_collections(self) -> None:
        self.collection_combo.clear()
        for col in library_store.list_collections():
            self.collection_combo.addItem(col["title"], col["id"])

    def _create_collection(self) -> None:
        name, ok = QInputDialog.getText(self, "Новая коллекция", "Название:")
        if not ok or not name.strip():
            return
        cid = library_store.create_collection(name.strip())
        self._reload_collections()
        idx = self.collection_combo.findData(cid)
        if idx >= 0:
            self.collection_combo.setCurrentIndex(idx)

    def _accept(self) -> None:
        new_name = self.new_collection.text().strip()
        if new_name:
            self._collection_id = library_store.create_collection(new_name)
        else:
            self._collection_id = self.collection_combo.currentData()
        if not self._collection_id:
            self.reject()
            return
        self.accept()

    @property
    def collection_id(self) -> Optional[str]:
        return self._collection_id
