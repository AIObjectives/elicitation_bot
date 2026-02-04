
import time
import pytest

from app.utils import blocklist_helpers


def test_default_ttl_fallback_on_missing_doc(monkeypatch):
    """Test that default TTL is used when Firestore doc doesn't exist."""
    blocklist_helpers._last_ttl_fetch = 0

    class FakeDoc:
        exists = False
        def to_dict(self):
            return {}

    class FakeDB:
        def collection(self, name):
            return self
        def document(self, name):
            return self
        def get(self):
            return FakeDoc()

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())
    ttl = blocklist_helpers._get_cache_ttl()
    assert ttl == blocklist_helpers._DEFAULT_TTL


def test_cache_update_logic(monkeypatch):
    """Test that TTL is correctly updated from Firestore."""
    blocklist_helpers._last_ttl_fetch = 0

    class FakeDoc:
        def __init__(self, exists=True):
            self.exists = exists
        def to_dict(self):
            return {"cache_ttl_seconds": 42}

    class FakeDB:
        def collection(self, name):
            assert name == "blocked_numbers"
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


def test_is_blocked_number_when_blocked(monkeypatch):
    """Test that is_blocked_number returns True for blocked number."""
    blocklist_helpers._cache.clear()

    class FakeDoc:
        exists = True

    class FakeDB:
        def collection(self, name):
            return self
        def document(self, phone):
            assert phone == "1234567890"
            return self
        def get(self):
            return FakeDoc()

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())
    monkeypatch.setattr(blocklist_helpers, "_get_cache_ttl", lambda: 60)

    result = blocklist_helpers.is_blocked_number("1234567890")
    assert result is True
    assert "1234567890" in blocklist_helpers._cache


def test_is_blocked_number_when_not_blocked(monkeypatch):
    """Test that is_blocked_number returns False for non-blocked number."""
    blocklist_helpers._cache.clear()

    class FakeDoc:
        exists = False

    class FakeDB:
        def collection(self, name):
            return self
        def document(self, phone):
            return self
        def get(self):
            return FakeDoc()

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())
    monkeypatch.setattr(blocklist_helpers, "_get_cache_ttl", lambda: 60)

    result = blocklist_helpers.is_blocked_number("9876543210")
    assert result is False


def test_is_blocked_number_error_handling(monkeypatch):
    """Test that is_blocked_number returns False on errors."""
    blocklist_helpers._cache.clear()

    class FakeDB:
        def collection(self, name):
            raise Exception("Database error")

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    result = blocklist_helpers.is_blocked_number("1234567890")
    assert result is False


def test_get_interaction_limit_from_event(monkeypatch):
    """Test that get_interaction_limit retrieves per-event limit."""
    blocklist_helpers._LIMIT_CACHE.clear()

    class FakeDoc:
        exists = True
        def to_dict(self):
            return {"interaction_limit": 100}

    class FakeDB:
        def collection(self, path):
            return self
        def document(self, doc):
            return self
        def get(self):
            return FakeDoc()

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    limit = blocklist_helpers.get_interaction_limit("test_event")
    assert limit == 100
    assert "test_event" in blocklist_helpers._LIMIT_CACHE


def test_get_interaction_limit_global_fallback(monkeypatch):
    """Test that get_interaction_limit falls back to global limit."""
    blocklist_helpers._LIMIT_CACHE.clear()

    call_count = [0]

    class FakeDoc:
        def __init__(self, exists, data):
            self.exists = exists
            self._data = data

        def to_dict(self):
            return self._data

    class FakeDB:
        def collection(self, path):
            return self

        def document(self, doc):
            return self

        def get(self):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: event-specific limit not found
                return FakeDoc(True, {})
            else:
                # Second call: global limit
                return FakeDoc(True, {"max_interactions_per_user": 200})

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    limit = blocklist_helpers.get_interaction_limit("test_event")
    assert limit == 200


def test_get_interaction_limit_default_fallback(monkeypatch):
    """Test that get_interaction_limit uses default when both event and global fail."""
    blocklist_helpers._LIMIT_CACHE.clear()

    class FakeDoc:
        exists = False
        def to_dict(self):
            return {}

    class FakeDB:
        def collection(self, path):
            return self
        def document(self, doc):
            return self
        def get(self):
            return FakeDoc()

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    limit = blocklist_helpers.get_interaction_limit("test_event")
    assert limit == blocklist_helpers._DEFAULT_LIMIT


def test_get_interaction_limit_caching(monkeypatch):
    """Test that get_interaction_limit caches results."""
    blocklist_helpers._LIMIT_CACHE["cached_event"] = {
        "value": 300,
        "time": time.time()
    }

    class FakeDB:
        def collection(self, path):
            raise AssertionError("Firestore should not be called for cached value")

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    limit = blocklist_helpers.get_interaction_limit("cached_event")
    assert limit == 300


def test_get_interaction_limit_error_handling(monkeypatch):
    """Test that get_interaction_limit returns default on errors."""
    blocklist_helpers._LIMIT_CACHE.clear()

    class FakeDB:
        def collection(self, path):
            raise Exception("Database error")

    monkeypatch.setattr(blocklist_helpers, "db", FakeDB())

    limit = blocklist_helpers.get_interaction_limit("test_event")
    assert limit == blocklist_helpers._DEFAULT_LIMIT
