# import firebase_admin
# from firebase_admin import credentials, firestore
# import logging

# # 1) Initialize Firebase
# cred = credentials.Certificate('xxxx')  # Change this to your Firebase service account JSON path
# firebase_admin.initialize_app(cred)
# db = firestore.client()

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)


# def initialize_event_collection(event_id, event_name, event_location, event_background, event_date, languages, initial_message, completion_message):
#     """
#     Creates (or overwrites) the Firestore document for this event_id under 'info'.
#     This sets the entire 'extra_questions' block at once.
    
#     WARNING: This will overwrite existing extra_questions and other fields in 'info'.
#     """
#     collection_ref = db.collection(f'AOI_{event_id}')
#     info_doc_ref = collection_ref.document('info')
    
#     # Example extra questions dict
#     extra_questions = {
#         "ExtraQuestion1": {
#             "enabled": True,
#             "id": "extract_name_with_llm",   # function ID if needed
#             "text": "How would you like to be addressed during this session? (Please feel free to use your own name, or another name)",
#             "order": 1
#         },
#         "ExtraQuestion2": {
#             "enabled": False,
#             "text": "現在請您於對話框輸入學號",
#             "order": 2
#         },
#         "ExtraQuestion3": {
#             "enabled": False,
#             "text": "現在請您於對話框輸入所屬學校",
#             "order": 3
#         },
#         "ExtraQuestion4": {
#             "enabled": False,   # This one won't be asked
#             "text": "Any special requests for the organizers?",
#             "order": 4
#         }
#     }

#     info_doc_ref.set({
#         'event_initialized': True,
#         'event_name': event_name,
#         'event_location': event_location,
#         'event_background': event_background,
#         'event_date': event_date,
#         'welcome_message': f"Please remember to record yourself every time you speak. How? When you’re ready to start speaking, hold the microphone button and slide it up to stay recording. Press send each time you finish speaking.",
#         'initial_message': initial_message,
#         'completion_message': completion_message,
#         'languages': languages,
#         'extra_questions': extra_questions,
#         'mode': 'listener'      # or "followup" / "survey"
#     })
    
#     logger.info(f"[initialize_event_collection] Event '{event_name}' initialized/overwritten with extra questions.")


# def add_extra_question(event_id, question_key, text, enabled=True, order=1, function_id=None):
#     """
#     Adds or updates a single extra question to the existing 'extra_questions' map
#     inside the 'info' document for the given event_id.
#     """
#     info_doc_ref = db.collection(f'{event_id}').document('info')
#     doc_snapshot = info_doc_ref.get()

#     if not doc_snapshot.exists:
#         logger.warning(f"Event '{event_id}' does not exist or has no 'info' doc. Please initialize it first.")
#         return

#     data = doc_snapshot.to_dict() or {}
#     extra_questions = data.get('extra_questions', {})

#     # Build a new question dictionary
#     new_question = {
#         "enabled": enabled,
#         "text": text,
#         "order": order
#     }
#     if function_id:
#         new_question["id"] = function_id

#     # Insert or update
#     extra_questions[question_key] = new_question

#     # Update Firestore
#     info_doc_ref.update({
#         "extra_questions": extra_questions
#     })
#     logger.info(f"[add_extra_question] Added/updated question '{question_key}' in event '{event_id}'.")


# if __name__ == "__main__":
#     # ---------------------------------------------------------------------
#     #  EXAMPLE USAGE 1: Initialize a brand new event (OVERWRITES everything)
#     # ---------------------------------------------------------------------
#     event_id = "ListenerMode2025Demo"
#     event_name = "Listener Mode 2025 Demo"
#     event_location = "Earth"
#     event_background = "The Listener Mode agent is designed to gather open-ended input from users in a natural, conversational flow. Instead of structured survey questions, it encourages free-form responses, making it ideal for collecting stories, reflections, or detailed feedback. The agent intelligently extracts key data such as event names, demographics, or themes using LLM-powered parsing. It’s especially useful in early engagement phases when user context is still unknown. The system is flexible and can prompt for clarification or follow-ups as needed."
#     event_date = "2025"
#     languages = ["Mandarin", "English"]
#     initial_message = "Thank you for joining this event! None of the data you provide will be directly linked back to you. Your identity is protected through secure and encrypted links."
#     completion_message = "Thank you for participating in this event. Your responses have been recorded."

#     initialize_event_collection(
#         event_id,
#         event_name,
#         event_location,
#         event_background,
#         event_date,
#         languages,
#         initial_message,
#         completion_message
#     )

#     # ---------------------------------------------------------------------
#     #  EXAMPLE USAGE 2: Add or update a single question
#     #  (Does NOT overwrite other existing questions)
#     # ---------------------------------------------------------------------
#     # add_extra_question(
#     #     event_id="DemoEvent2025",
#     #     question_key="ExtraQuestion5",
#     #     text="What is your favorite color?",
#     #     enabled=True,
#     #     order=5,
#     #     function_id=None
#     # )

#     # add_extra_question(
#     #     event_id="DemoEvent2025",
#     #     question_key="ExtraQuestion6",
#     #     text="Please tell me more about your background.",
#     #     enabled=True,
#     #     order=6,
#     #     function_id=None
#     # )

#     # You can comment out one or the other example usage block as needed.
#     # Just run this file to update your Firestore accordingly.






import firebase_admin
from firebase_admin import credentials, firestore
import logging

# 1) Initialize Firebase
cred = credentials.Certificate('/Users/emreturan/Desktop/firebase2/AOIFIREBASE/aoiwhatsappbot1-firebase-adminsdk-fbsvc-748e2a2606.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Configure logging
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
    
    # Example extra questions dict
    extra_questions = {
        "ExtraQuestion1": {
            "enabled": True,
            "id": "extract_name_with_llm",   # function ID if needed
            "text": "How would you like to be addressed during this session? (Please feel free to use your own name, or another name)",
            "order": 1
        },
        "ExtraQuestion2": {
            "enabled": False,
            "text": "現在請您於對話框輸入學號",
            "order": 2
        },
        "ExtraQuestion3": {
            "enabled": False,
            "text": "現在請您於對話框輸入所屬學校",
            "order": 3
        },
        "ExtraQuestion4": {
            "enabled": False,   # This one won't be asked
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
        'welcome_message': f"Please remember to record yourself every time you speak. How? When you’re ready to start speaking, hold the microphone button and slide it up to stay recording. Press send each time you finish speaking.",
        'initial_message': initial_message,
        'completion_message': completion_message,
        'languages': languages,
        'language_guidance': language_guidance,
        'extra_questions': extra_questions,
        'mode': 'listener'      # or "followup" / "survey"
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

    # Insert or update
    extra_questions[question_key] = new_question

    # Update Firestore
    info_doc_ref.update({
        "extra_questions": extra_questions
    })
    logger.info(f"[add_extra_question] Added/updated question '{question_key}' in event '{event_id}'.")


if __name__ == "__main__":
    # ---------------------------------------------------------------------
    #  EXAMPLE USAGE 1: Initialize a brand new event (OVERWRITES everything)
    # ---------------------------------------------------------------------
    event_id = "EnglishListener2025Demo"
    event_name = "EnglishListener2025Demo"
    event_location = "Earth"
    event_background = "The Listener Mode agent is designed to gather open-ended input from users in a natural, conversational flow. Instead of structured survey questions, it encourages free-form responses, making it ideal for collecting stories, reflections, or detailed feedback. The agent intelligently extracts key data such as event names, demographics, or themes using LLM-powered parsing. It’s especially useful in early engagement phases when user context is still unknown. The system is flexible and can prompt for clarification or follow-ups as needed."
    event_date = "2025"
    languages = ["Mandarin", "English"]
    language_guidance = "The bot should prioritize matching the user's language when detected, but default to English if unclear. Avoid switching languages mid-conversation."

    initial_message = "Thank you for joining this event! None of the data you provide will be directly linked back to you. Your identity is protected through secure and encrypted links."
    completion_message = "Thank you for participating in this event. Your responses have been recorded."

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
