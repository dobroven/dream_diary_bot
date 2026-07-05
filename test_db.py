import os
import tempfile
import pytest
import db


@pytest.fixture(autouse=True)
def temp_db():
    """Replace DB_PATH with a temporary file and init tables."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    orig_path = db.DB_PATH
    db.DB_PATH = tmp.name
    db.init_db()
    yield
    db.DB_PATH = orig_path
    os.unlink(tmp.name)


def test_add_and_list():
    dream_id = db.add_dream(1, "Test Title", "Test Description")
    assert dream_id is not None

    rows = db.list_dreams(1)
    assert len(rows) == 1
    assert rows[0]["title"] == "Test Title"
    assert rows[0]["description"] == "Test Description"


def test_list_pagination():
    for i in range(7):
        db.add_dream(1, f"Title {i}", f"Desc {i}")

    page1 = db.list_dreams(1, limit=3, offset=0)
    assert len(page1) == 3
    assert page1[0]["title"] == "Title 6"  # newest first

    page2 = db.list_dreams(1, limit=3, offset=3)
    assert len(page2) == 3
    assert page2[0]["title"] == "Title 3"

    page3 = db.list_dreams(1, limit=3, offset=6)
    assert len(page3) == 1
    assert page3[0]["title"] == "Title 0"


def test_search():
    db.add_dream(1, "Весенний сон", "Я летал во сне")
    db.add_dream(1, "Кошмар", "Меня преследовали")
    db.add_dream(1, "Рыбалка", "Ловил рыбу на озере")

    # "сон" matches title "Весенний сон"
    rows = db.search_dreams(1, "сон")
    assert len(rows) == 1

    # "летал" matches description of first row
    rows = db.search_dreams(1, "летал")
    assert len(rows) == 1

    rows = db.search_dreams(1, "РЫБА")
    assert len(rows) == 1
    assert rows[0]["title"] == "Рыбалка"

    # case-insensitive Cyrillic search
    rows = db.search_dreams(1, "ВЕСЕННИЙ СОН")
    assert len(rows) == 1

    rows = db.search_dreams(1, "СОН")
    assert len(rows) == 1


def test_user_isolation():
    uid1 = 10
    uid2 = 20

    db.add_dream(uid1, "A", "desc A")
    db.add_dream(uid1, "B", "desc B")
    db.add_dream(uid2, "C", "desc C")

    assert db.count_dreams(uid1) == 2
    assert db.count_dreams(uid2) == 1
    assert len(db.list_dreams(uid1)) == 2
    assert len(db.list_dreams(uid2)) == 1

    assert db.search_dreams(uid1, "A") != []
    assert db.search_dreams(uid2, "A") == []


def test_get_dream():
    dream_id = db.add_dream(1, "GetTest", "GetDescription")
    row = db.get_dream(1, dream_id)
    assert row is not None
    assert row["title"] == "GetTest"

    # wrong user
    row2 = db.get_dream(999, dream_id)
    assert row2 is None


def test_delete_by_id():
    dream_id = db.add_dream(1, "Delete me", "bye")
    assert db.delete_dream(1, dream_id) is True
    assert db.get_dream(1, dream_id) is None


def test_delete_by_title():
    db.add_dream(1, "Уникальный заголовок", "описание")
    assert db.delete_dream_by_title(1, "уникальный ЗАГОЛОВОК") is True
    assert db.count_dreams(1) == 0


def test_delete_cross_user():
    dream_id = db.add_dream(1, "Shared", "data")
    assert db.delete_dream(999, dream_id) is False  # different user
    assert db.get_dream(1, dream_id) is not None


def test_count_dreams():
    assert db.count_dreams(1) == 0
    db.add_dream(1, "T1", "D1")
    assert db.count_dreams(1) == 1


def test_get_dream_by_title():
    db.add_dream(1, "Hello", "World")
    row = db.get_dream_by_title(1, "hello")
    assert row is not None
    assert row["title"] == "Hello"

    row2 = db.get_dream_by_title(2, "hello")
    assert row2 is None


def test_count_dreams_by_title():
    db.add_dream(1, "Уникальный", "desc")
    db.add_dream(1, "Общий", "desc")
    db.add_dream(1, "Общий", "desc2")
    db.add_dream(2, "Общий", "other")

    assert db.count_dreams_by_title(1, "Уникальный") == 1
    assert db.count_dreams_by_title(1, "общий") == 2
    assert db.count_dreams_by_title(1, "НЕТ") == 0
    assert db.count_dreams_by_title(2, "Общий") == 1


def test_update_dream():
    dream_id = db.add_dream(1, "Old Title", "Old Description", "2024-01-01")
    assert dream_id is not None

    ok = db.update_dream(1, dream_id, "New Title", "New Description", "2024-06-15")
    assert ok is True

    row = db.get_dream(1, dream_id)
    assert row["title"] == "New Title"
    assert row["description"] == "New Description"
    assert row["date"] == "2024-06-15"

    # wrong user
    ok2 = db.update_dream(999, dream_id, "X", "Y", "2024-01-01")
    assert ok2 is False


def test_list_all_dreams():
    for i in range(5):
        db.add_dream(1, f"Title {i}", f"Desc {i}")
    db.add_dream(2, "Other", "other")

    rows = db.list_all_dreams(1)
    assert len(rows) == 5
    assert rows[0]["title"] == "Title 4"  # newest first

    rows2 = db.list_all_dreams(2)
    assert len(rows2) == 1
    assert rows2[0]["title"] == "Other"
