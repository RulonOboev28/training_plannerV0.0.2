import json
from pathlib import Path

import pytest

from core import library_store
from core.models import Exercise, HierarchyLevel


@pytest.fixture()
def isolated_library(tmp_path, monkeypatch):
    lib_file = tmp_path / "library.json"
    monkeypatch.setattr(library_store, "LIBRARY_FILE", lib_file)
    yield lib_file


def test_create_collection_and_add(isolated_library):
    cid = library_store.create_collection("Силовые")
    ex = Exercise(title="Жим")
    entry = library_store.add_element(ex, cid)
    data = json.loads(isolated_library.read_text(encoding="utf-8"))
    assert len(data["collections"]) == 1
    col = next(c for c in data["collections"] if c["id"] == cid)
    assert col["entries"][0]["title"] == "Жим"
    assert entry["id"]


def test_move_entry_between_collections(isolated_library):
    c1 = library_store.create_collection("A")
    c2 = library_store.create_collection("B")
    e1 = library_store.add_element(Exercise(title="1"), c1)
    library_store.add_element(Exercise(title="2"), c1)
    assert library_store.move_entry(c1, e1["id"], c2, 0)
    cols = {c["id"]: c for c in library_store.list_collections()}
    assert len(cols[c1]["entries"]) == 1
    assert cols[c2]["entries"][0]["title"] == "1"


def test_migrate_flat_list(isolated_library):
    isolated_library.write_text(
        json.dumps([{
            "title": "Old",
            "type": "exercise",
            "level": HierarchyLevel.EXERCISE.value,
            "payload": Exercise(title="Old").to_dict(),
        }], ensure_ascii=False),
        encoding="utf-8",
    )
    lib = library_store.load_library()
    assert lib["version"] == 2
    assert lib["collections"][0]["entries"][0]["title"] == "Old"
