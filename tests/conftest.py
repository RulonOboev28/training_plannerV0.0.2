"""Общая конфигурация тестов.

Тесты, которым нужны Qt-объекты, используют фикстуру `qapp` с offscreen-платформой,
чтобы работать без реального дисплея (в т.ч. в CI).
"""
import os
import sys
from pathlib import Path

import pytest

# гарантируем, что корень проекта в путях импорта
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
