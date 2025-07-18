from config.config import db
from datetime import datetime

def initialize_user_document(event_id: str, normalized_phone: str) -> dict:
    """
    Create or merge a user doc under AOI_{event_id} with:
      - interactions: []
      - name: None
      - questions_asked: { "<q_id>": False, ... }
      - responses: {}
      - last_question_id: None
      - survey_complete: False
    """
    info_ref = db.collection(f"AOI_{event_id}").document("info")
    info_doc = info_ref.get()
    if not info_doc.exists:
        raise ValueError(f"No event info for {event_id}")

    questions = info_doc.to_dict().get("questions", [])
    questions_asked = { str(q["id"]): False for q in questions }

    user_ref = db.collection(f"AOI_{event_id}").document(normalized_phone)
    payload = {
        "interactions": [],
        "name": None,
        "questions_asked": questions_asked,
        "responses": {},
        "last_question_id": None,
        "survey_complete": False
    }
    user_ref.set(payload, merge=True)
    return payload
