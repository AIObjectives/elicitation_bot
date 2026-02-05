import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os, json

FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not FIREBASE_CREDENTIALS_JSON:
    raise RuntimeError("Missing FIREBASE_CREDENTIALS_JSON environment variable")

cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))
firebase_admin.initialize_app(cred)
db = firestore.client()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_event_collection(event_id, event_name, event_location, event_background, event_date, languages, language_guidance, initial_message, completion_message):
    """
    Creates (or overwrites) the Firestore document for this event_id under 'info'.
    This sets the entire 'extra_questions' block at once.
    
    WARNING: This will overwrite existing extra_questions and other fields in 'info'.
    """
    collection_ref = db.collection(f'AOI_{event_id}')
    info_doc_ref = collection_ref.document('info')
    
    extra_questions = {
        "ExtraQuestion1": {
            "enabled": False,
            "id": "extract_name_with_llm",   
            "text": "How would you like to be addressed during this session? (Please feel free to use your own name, or another name)",
            "order": 1
        },
        "ExtraQuestion2": {
            "enabled": True,
            "text": "Please provide the sector you are most affiliated with, such as business, government, academia, civil society. ",
            "order": 2
        },
        "ExtraQuestion3": {
            "enabled": False,
            "text": "現在請您於對話框輸入所屬學校",
            "order": 3
        },
        "ExtraQuestion4": {
            "enabled": False, 
            "text": "Any special requests for the organizers?",
            "order": 4
        }
    }

    info_doc_ref.set({
        'event_initialized': True,
        'event_name': event_name,
        'event_location': event_location,
        'event_background': event_background,
        'event_date': event_date,
        'welcome_message': f'Welcome to CES2025 panel "Breaking down political barriers and solving problems through civic dialogue: What is it, and how can it be scaled?"',
        'initial_message': initial_message,
        'completion_message': completion_message,
        'languages': languages,
        'language_guidance': language_guidance,
        'extra_questions': extra_questions,
        'mode': 'listener',      # or "followup" / "survey"
        'interaction_limit': 450,  # Default; can be customized per event later
        'default_model': 'gpt-4o-mini',



        'second_round_prompts': {
            'system_prompt': (
                "You are a concise, context-aware *second-round deliberation* assistant.\n"
                "Goals: keep flow natural, avoid repetition, and deepen the user's thinking with concrete contrasts.\n"
                "Hard rules:\n"
                "- NEVER re-introduce the whole setup after the intro.\n"
                "- Keep replies short: 1–4 crisp sentences, <= ~400 characters total.\n"
                "- Answer the user's exact question first; then, if helpful, add ONE brief nudge.\n"
                "- Do not ask generic questions like 'What aspect...?'—be specific and grounded.\n"
                "- Only restate claims if the user asks for them.\n"
            ),
            'user_prompt': (
                "{history_block}"
                "User Summary: {summary}\n"
                "Report Metadata (context only): {metadata}\n"
                "Agreeable (grounding): {agree_block}\n"
                "Opposing (grounding): {oppose_block}"
                "{reason_line}\n\n"
                "Current user message: {user_msg}\n\n"
                "Respond now following the rules above. If the user asks 'what are we doing', reply with ONE sentence and pivot to a pointed follow-up.\n"
                "If the user asks whether you can access others' reports, answer briefly: you have curated claims (not direct personal data), then offer a one-line, targeted next step.\n"
                "When relevant, introduce another participant’s claim naturally, e.g., 'Here’s something that aligns with your view—do you agree?' or 'Here’s an opposing view—how would you respond?'\n"
     
            )
        },

        'second_round_claims_source': {
        'enabled': False,  # Change to True via Firestore UI to activate 2nd round
        'collection': '2ndRoundDeliberationTests',
        'document': 'AI_Manifestos__c4340250__part1'
    }

        

        

        
    })
    
    logger.info(f"[initialize_event_collection] Event '{event_name}' initialized/overwritten with extra questions.")




def add_extra_question(event_id, question_key, text, enabled=True, order=1, function_id=None):
    """
    Adds or updates a single extra question to the existing 'extra_questions' map
    inside the 'info' document for the given event_id.
    """
    info_doc_ref = db.collection(f'{event_id}').document('info')
    doc_snapshot = info_doc_ref.get()

    if not doc_snapshot.exists:
        logger.warning(f"Event '{event_id}' does not exist or has no 'info' doc. Please initialize it first.")
        return

    data = doc_snapshot.to_dict() or {}
    extra_questions = data.get('extra_questions', {})

    # Build a new question dictionary
    new_question = {
        "enabled": enabled,
        "text": text,
        "order": order
    }
    if function_id:
        new_question["id"] = function_id

    
    extra_questions[question_key] = new_question

    info_doc_ref.update({
        "extra_questions": extra_questions
    })
    logger.info(f"[add_extra_question] Added/updated question '{question_key}' in event '{event_id}'.")


if __name__ == "__main__":
    # ---------------------------------------------------------------------
    #  EXAMPLE USAGE 1: Initialize a brand new event (OVERWRITES everything)
    # ---------------------------------------------------------------------
    event_id = "listenerdynamicTest1"
    event_name = "listenerdynamicTest1"
    event_location = "Stockton, CA"
    event_background = "The California Economic Summit is a dynamic, solutions-driven gathering where leaders from across the state come together to support economic advancement strategies that are regions-up and focused on the growth and stewardship of California’s valuable communities, land, and resources."
    event_date = "2025-10-23"
    languages = ["Spanish", "English"]
    language_guidance = "The bot should prioritize matching the user's language when detected, but default to English if unclear. Avoid switching languages mid-conversation."
    initial_message = "Your insights will make this panel stronger. This bot is here to help you contribute!"
    completion_message = "Thank you for your participation. Your responses have been recorded!"

    initialize_event_collection(
        event_id,
        event_name,
        event_location,
        event_background,
        event_date,
        languages,
        language_guidance,  
        initial_message,
        completion_message
    )
