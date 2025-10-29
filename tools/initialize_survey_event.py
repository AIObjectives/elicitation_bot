import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Form, Response
import logging
from uuid import uuid4
import os, json

FIREBASE_CREDENTIALS_JSON = os.environ.get("FIREBASE_CREDENTIALS_JSON")

if not FIREBASE_CREDENTIALS_JSON:
    raise RuntimeError("Missing FIREBASE_CREDENTIALS_JSON environment variable")

cred = credentials.Certificate(json.loads(FIREBASE_CREDENTIALS_JSON))

firebase_admin.initialize_app(cred)
db = firestore.client()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_event_collection(
    event_id,
    event_name,
    event_location,
    event_background,
    event_date,
    languages,
    welcome_message,
    initial_message,
    next_message,
    questions,
    completion_message,
    extra_questions
):
    

    collection_ref = db.collection(f'AOI_{event_id}')
    info_doc_ref = collection_ref.document('info')

    formatted_questions = []
    for idx, question in enumerate(questions):
        formatted_questions.append({
            "id": idx,
            "text": question,
            "asked_count": 0
        })

    info_doc_ref.set({
        'event_initialized': True,
        'event_name': event_name,
        'event_location': event_location,
        'event_background': event_background,
        'event_date': event_date,
        'languages': languages,
        'welcome_message': welcome_message,
        'initial_message': initial_message,
        'next_message': next_message,
        'questions': formatted_questions,
        'completion_message': completion_message,
        'extra_questions': extra_questions,
        'mode': 'survey',      # or "followup" / "survey"
        'interaction_limit': 450  # Default; can be customized per event later

    })

    logger.info(f"Event '{event_name}' initialized with {len(formatted_questions)} survey questions and {len(extra_questions)} extra questions.")

if __name__ == "__main__":
    # ConnexUs Survey 2025 - Survey Mode
    event_id = "SurveyMode2025Demo"
    event_name = "Survey Mode 2025 Demo"
    event_location = "online"
    event_date = "2025"
    event_background = "This WhatsApp agent is designed to conduct quick and engaging surveys directly through chat. It can collect user responses in real time, support multiple languages, and adapt its tone based on the audience. Whether it's gathering feedback after an event, running a community poll, or collecting research data, the agent ensures a smooth, conversational experience. It also stores responses securely and can trigger follow-up messages based on answers. The system is fully customizable to fit different survey flows and objectives. "
    languages = ["English", "Arabic", "French", "Spanish", "Kurdish", "Russian"]

    initial_message = "Welcome to the Survey Mode Demo! We greatly value your experiences and feedback. Your responses will be secure and used to improve the platform."
    welcome_message = "Thank you for your input. There are X questions now for your reflection and response. Please respond to each question in a single message only - by text or voice. Are you ready to start?"

    next_message = ""  # Not applicable in this case
    completion_message = "Thank you for your time and participation! Your responses have been recorded."

    # Main Survey Questions (excluding first 3 which will go as extra questions)
    questions = [
        "How would you rate your overall experience with xxxx on a scale of 1-5 (1 = Very Poor, 5 = Excellent)?",
        "What do you like most about xxxx?",
        "How easy is it to use the platform?",
        "Have you faced any difficulties while using xxx? If so, what have they been?",
        "Which xxx feature(s) do you use most often?",
        "What additional features would improve your experience on xxx?",
        "How could we better support your goals through xxx? For example: enhanced networking opportunities, improved user interface, more guidance, etc.",
        "How likely are you to recommend xxx to others on a scale of 1-5 (1 = Not Likely, 5 = Very Likely)? Please explain your response if possible.",
        "Please share any final comments or suggestions for xxx."
    ]

    # Extra Questions (the first 3 as requested)
    extra_questions = {

         "ExtraQuestion1": {
            "enabled": False,
            "id": "extract_name_with_llm",  # function ID if needed
            "text": "How would you like to be addressed during this session? (Please feel free to use your own name, or another name)",
            "order": 1
        },
        "ExtraQuestion2": {
            "enabled": False,
            "id": "specialization_area",
            "text": "What area(s) do you specialize in (for ex. peacebuilding, development, environment, youth, technology, etc.)?",
            "order": 2
        },
        "ExtraQuestion3": {
            "enabled": False,
            "id": "location_info",
            "text": "Where are you located (city and/or country)?",
            "order": 3
        },
        "ExtraQuestion4": {
            "enabled": True,
            "id": "referral_source",
            "text": "How did you hear about xxx?",
            "order": 4
        }
    }



    initialize_event_collection(
        event_id,
        event_name,
        event_location,
        event_background,
        event_date,
        languages,
        welcome_message,
        initial_message,
        next_message,
        questions,
        completion_message,
        extra_questions
    )
