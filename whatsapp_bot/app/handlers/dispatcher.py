
from fastapi import HTTPException, Response
from config.config import db
from app.handlers.ListenerMode import reply_listener
from app.handlers.FollowupMode import reply_followup
from app.handlers.SurveyMode import reply_survey

async def dispatch_message(Body: str, From: str, MediaUrl0: str = None):
    """
    Dispatcher that routes incoming WhatsApp messages to the appropriate mode handler.
    Each handler is responsible for managing user state and event ID logic internally.
    """

    # Normalize phone number
    normalized_phone = From.replace("+", "").replace("-", "").replace(" ", "")
    user_ref = db.collection("user_event_tracking").document(normalized_phone)
    user_doc = user_ref.get().to_dict() or {}

    current_event_id = user_doc.get("current_event_id")
    if not current_event_id:
        # Let the handler (e.g., listener) manage missing event_id state
        return await reply_listener(Body, From, MediaUrl0)

    # Fetch mode from Firestore
    info = db.collection(f"AOI_{current_event_id}").document("info").get()
    if not info.exists:
        raise HTTPException(status_code=400, detail="Unknown event ID")

    mode = info.to_dict().get("mode", "listener").lower()

    # Route to the correct mode handler
    if mode == "listener":
        return await reply_listener(Body, From, MediaUrl0)
    elif mode == "followup":
        return await reply_followup(Body, From, MediaUrl0)
    elif mode == "survey":
        return await reply_survey(Body, From, MediaUrl0)
    else:
        raise HTTPException(status_code=500, detail=f"Unrecognized mode '{mode}'")
