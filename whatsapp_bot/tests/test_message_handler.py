
# ⚠️ NOTE: This test suite is not fully verified end-to-end; use the main production version or follow the README to test locally via Twilio sandbox.

from fastapi.testclient import TestClient
import pytest

from app.main import app
from config.config import db

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_firestore(monkeypatch):
    """
    Monkey-patch Firestore calls so that unit tests do not hit the real database.
    You can either:
      1) Use the Firebase emulator locally (preferred), OR
      2) Stub out `db.collection(...)` methods entirely.
    For simplicity, this fixture ensures no actual Firestore writes occur.
    """
    class DummyDoc:
        def __init__(self):
            self._data = {}
        def get(self):
            return type("OBJ", (), {"exists": False})
        def set(self, data):
            self._data = data
        def update(self, data):
            self._data.update(data)

    class DummyCollection:
        def __init__(self):
            self._docs = {}
        def document(self, key):
            if key not in self._docs:
                self._docs[key] = DummyDoc()
            return self._docs[key]

    class DummyDB:
        def __init__(self):
            self._cols = {}
        def collection(self, name):
            if name not in self._cols:
                self._cols[name] = DummyCollection()
            return self._cols[name]

    monkeypatch.setattr(db, "__class__", DummyDB)
    # If code does direct calls like db.collection(...).document(...), we need:
    monkeypatch.setattr(db, "collection", DummyDB().collection)

def test_missing_body_returns_422():
    """
    - /message/ requires both Body and From form fields.
    - If Body is missing, FastAPI should return 422 (Unprocessable Entity).
    """
    response = client.post("/message/", data={"From": "+100200300"})
    assert response.status_code == 422

def test_missing_from_returns_422():
    """
    - /message/ requires `From`. Missing it → 422.
    """
    response = client.post("/message/", data={"Body": "hello"})
    assert response.status_code == 422

def test_no_current_event_prompts_for_event_id(monkeypatch):
    """
    Simulate a user who has no current_event_id in their Firestore doc.
    Expectation: the response text will ask for an event ID.
    """
    # We need to ensure that db.collection('user_event_tracking').document(...) returns a doc whose .get().exists == True
    class DummyDocExists:
        def get(self):
            return type("OBJ", (), {"exists": True})
        def to_dict(self):
            return {
                "events": [],
                "current_event_id": None,
                "awaiting_event_id": False,
                "awaiting_event_change_confirmation": False,
                "last_inactivity_prompt": None,
                "awaiting_extra_questions": False,
                "current_extra_question_index": 0,
                "invalid_attempts": 0
            }
        def update(self, data):
            pass
        def set(self, data):
            pass

    class DummyCollectionExists:
        def document(self, key):
            return DummyDocExists()

    monkeypatch.setattr(db, "collection", lambda name: DummyCollectionExists())

    response = client.post(
        "/message/",
        data={"Body": "anything", "From": "+1234567890"}
    )
    assert response.status_code == 200
    assert "provide your event ID" in response.text.lower()

@pytest.mark.parametrize("body_text, expected_substring", [
    ("finalize", "thank you"),
    ("finish", "thank you"),
])
def test_finalize_sends_completion(monkeypatch, body_text, expected_substring):
    """
    If the user sends "finalize" or "finish", the bot replies with a completion message.
    """
    # Make Firestore return an existing event so we bypass earlier steps.
    class DummyInfoDoc:
        def get(self):
            return type("OBJ", (), {"exists": True})
        def to_dict(self):
            return {"completion_message": "Survey complete!"}

    class DummyParticipantDoc:
        def get(self):
            return type("OBJ", (), {"exists": True})
        def to_dict(self):
            return {"name": "Alice", "interactions": [], "event_id": "E1"}

    class DummyUserTrackingDoc:
        def get(self):
            return type("OBJ", (), {"exists": True})
        def to_dict(self):
            return {
                "events": [{"event_id": "E1", "timestamp": datetime.utcnow().isoformat()}],
                "current_event_id": "E1",
                "awaiting_event_id": False,
                "awaiting_event_change_confirmation": False,
                "last_inactivity_prompt": None,
                "awaiting_extra_questions": False,
                "current_extra_question_index": 0,
                "invalid_attempts": 0
            }
        def update(self, data):
            pass

    class DummyCollection:
        def __init__(self, name):
            self.name = name
        def document(self, key):
            if self.name.endswith("_tracking"):
                return DummyUserTrackingDoc()
            if self.name == "AOI_E1":
                return DummyParticipantDoc()
            if self.name == "AOI_E1_info":
                return DummyInfoDoc()
            return type("OBJ", (), {"exists": False})

    monkeypatch.setattr(db, "collection", lambda name: DummyCollection(name))

    response = client.post(
        "/message/",
        data={"Body": body_text, "From": "+1234567890"}
    )
    assert response.status_code == 200
    assert "survey complete!" in response.text.lower()

def test_invalid_event_selection_after_inactivity(monkeypatch):
    """
    Simulate:
      1) user was inactive, got prompted with event list
      2) user replies "99" which is invalid (no such index)
      3) user gets asked again (invalid attempts < 2)
    """
    # Step A: Let user_events = [ {event_id:"E1", timestamp:...} ], last_inactivity_prompt exists
    # Step B: Body="99" → invalid_attempts becomes 1, reply includes "invalid event selection"
    class DummyUserTrackingDocA:
        def __init__(self):
            self.data = {
                "events": [{"event_id": "E1", "timestamp": (datetime.utcnow() - timedelta(days=1, hours=1)).isoformat()}],
                "current_event_id": "E1",
                "awaiting_event_id": False,
                "awaiting_event_change_confirmation": False,
                "last_inactivity_prompt": (datetime.utcnow() - timedelta(hours=25)).isoformat(),
                "awaiting_extra_questions": False,
                "current_extra_question_index": 0,
                "invalid_attempts": 0
            }
        def get(self):
            return type("OBJ", (), {"exists": True, "to_dict": lambda: self.data})
        def to_dict(self):
            return self.data
        def update(self, new_data):
            self.data.update(new_data)

    class DummyCollection:
        def __init__(self, name):
            self.name = name
        def document(self, key):
            if name.endswith("user_event_tracking"):
                return DummyUserTrackingDocA()
            return type("OBJ", (), {"exists": False})

    monkeypatch.setattr(db, "collection", lambda name: DummyCollection(name))

    response = client.post(
        "/message/",
        data={"Body": "99", "From": "+1234567890"}
    )
    assert response.status_code == 200
    assert "invalid event selection" in response.text.lower()

# (Add more parametric tests for steps like “change name”, “change event”, extra questions, etc.)
def test_valid_event_selection_after_inactivity(monkeypatch):
    """
    Simulate:
      1) user was inactive, got prompted with event list
      2) user replies "1" which is valid (selects first event)
      3) user gets confirmation message
    """
    # Step A: Let user_events = [ {event_id:"E1", timestamp:...} ], last_inactivity_prompt exists
    # Step B: Body="1" → current_event_id becomes "E1", reply includes "event changed"
    class DummyUserTrackingDocB:
        def __init__(self):
            self.data = {
                "events": [{"event_id": "E1", "timestamp": (datetime.utcnow() - timedelta(days=1, hours=1)).isoformat()}],
                "current_event_id": None,
                "awaiting_event_id": False,
                "awaiting_event_change_confirmation": False,
                "last_inactivity_prompt": (datetime.utcnow() - timedelta(hours=25)).isoformat(),
                "awaiting_extra_questions": False,
                "current_extra_question_index": 0,
                "invalid_attempts": 0
            }
        def get(self):
            return type("OBJ", (), {"exists": True, "to_dict": lambda: self.data})
        def to_dict(self):
            return self.data
        def update(self, new_data):
            self.data.update(new_data)

    class DummyCollection:
        def __init__(self, name):
            self.name = name
        def document(self, key):
            if name.endswith("user_event_tracking"):
                return DummyUserTrackingDocB()
            return type("OBJ", (), {"exists": False})

    monkeypatch.setattr(db, "collection", lambda name: DummyCollection(name))

    response = client.post(
        "/message/",
        data={"Body": "1", "From": "+1234567890"}
    )
    assert response.status_code == 200
    assert "event changed to E1" in response.text.lower()



