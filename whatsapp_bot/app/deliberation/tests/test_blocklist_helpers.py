
import time
import pytest

from app.utils import blocklist_helpers


def test_default_ttl_is_int():
    ttl = blocklist_helpers._get_cache_ttl()
    assert isinstance(ttl, int)
    assert ttl > 0


def test_cache_update_logic(monkeypatch):
    blocklist_helpers._last_ttl_fetch = 0

    class FakeDoc:
        def __init__(self, exists=True):
            self.exists = exists
        def to_dict(self):
            return {"cache_ttl_seconds": 42}

    class FakeDB:
        def collection(self, name):
            assert name == "system_settings" or name == "blocked_numbers"
            return self
        def document(self, name):
            return self
        def get(self):
            return FakeDoc()

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    ttl = blocklist_helpers._get_cache_ttl()
    assert ttl == 42, "TTL should update from Firestore mock"


def test_cache_reuse(monkeypatch):
    """Ensures cached TTL is reused within refresh interval."""
    blocklist_helpers._ttl_value = 99
    blocklist_helpers._last_ttl_fetch = time.time()

    class FakeDB:
        def collection(self, *_):
            raise AssertionError("Firestore should not be called")
    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    ttl = blocklist_helpers._get_cache_ttl()
    assert ttl == 99


def test_is_blocked_number_caching(monkeypatch):
    """Tests that cached phone results are reused correctly."""
    fake_phone = "12345"
    now = time.time()
    blocklist_helpers._cache[fake_phone] = {"value": True, "time": now}

    class FakeDB:
        def collection(self, *_):
            raise AssertionError("Firestore should not be called")
    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    result = blocklist_helpers.is_blocked_number(fake_phone)
    assert result is True
