from app.services.firestore_service import EventService, ParticipantService

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
    # Get event info and questions using EventService
    event_info = EventService.get_event_info(event_id)
    if not event_info:
        raise ValueError(f"No event info for {event_id}")

    questions = EventService.get_survey_questions(event_id)
    questions_asked = { str(q["id"]): False for q in questions }

    # Prepare survey-specific participant data
    payload = {
        "interactions": [],
        "name": None,
        "questions_asked": questions_asked,
        "responses": {},
        "last_question_id": None,
        "survey_complete": False
    }

    # Initialize participant using ParticipantService
    # First ensure basic participant document exists
    ParticipantService.initialize_participant(event_id, normalized_phone)
    # Then update with survey-specific fields (merge=True behavior)
    ParticipantService.update_participant(event_id, normalized_phone, payload)

    return payload
