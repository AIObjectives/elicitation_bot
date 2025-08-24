
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI, Form, Response
import logging
from uuid import uuid4

# Initialize Firebase
cred = credentials.Certificate('/Users/emreturan/Desktop/firebase2/AOIFIREBASE/aoiwhatsappbot1-firebase-adminsdk-fbsvc-748e2a2606.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Example extra questions dict from listener mode
extra_questions = {
    "ExtraQuestion1": {
        "enabled": False,
        "id": "extract_name_with_llm",
        "text": "How would you like to be addressed during this session? (Please feel free to use your own name, or another name)",
        "order": 1
    },
    "ExtraQuestion2": {
        "enabled": True,
        "text": "Please remember to record yourself every time you speak. How? When you’re ready to start speaking, hold the microphone button and slide it up to stay recording. Press send each time you finish speaking. Are you ready to start?",
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


def initialize_event_collection(
    event_id,
    event_name,
    event_location,
    event_background,
    event_date,
    bot_topic,
    bot_aim,
    bot_principles,
    bot_personality,
    bot_additional_prompts,
    main_question,
    languages,
    language_guidance,
    initial_message,
    completion_message
):
    """Initializes the Firestore collection and stores event info, bot settings, survey questions,
    follow-up questions, and extra questions within the 'info' document."""

    collection_ref = db.collection(f'AOI_{event_id}')
    info_doc_ref = collection_ref.document('info')
    
    # Define the follow-up questions
    follow_up_questions = [
        "Can you elaborate on what stood out to you the most about X?",
        "How did X make you feel, and why do you think that is?",
        "What aspects of X do you think work well, and what could be improved?",
        "Can you share an example or experience that relates to your impression of X?",
        "What specific elements of X influenced your thoughts the most?",
        "Did anything about X surprise you or challenge your expectations?",
        "If you were to explain X to someone else, how would you describe it?",
        "What additional context or information do you think would be helpful when discussing X?",
        "Are there any aspects of X that you think are being overlooked or under-discussed?",
        "What would you recommend as the next step or action based on your impressions of X?",
        "Do you think X aligns with your initial expectations? Why or why not?",
        "What do you think could be added to X to make it more engaging or effective?",
        "How does X compare to similar experiences or ideas you've encountered before?",
        "What questions or concerns come to mind when you think about X?",
        "If you had to summarize your overall impression of X in one sentence, what would it be?"
    ]

    # Add a toggle for the follow-up questions
    follow_up_toggle = {
        "enabled": True,  # Set to False to turn off follow-up questions
        "questions": follow_up_questions
    }

    # Set the main event info in the 'info' document
    info_doc_ref.set({
        'event_initialized': True,
        'event_name': event_name,
        'event_location': event_location,
        'event_background': event_background,
        'event_date': event_date,
        'welcome_message': f"What could make you change your mind about who you would vote for?",
        'initial_message': initial_message,
        'completion_message': completion_message,
        
        'bot_topic': bot_topic,
        'main_question': main_question,
        'bot_aim': bot_aim,
        'bot_principles': bot_principles,
        'bot_personality': bot_personality,
        'bot_additional_prompts': bot_additional_prompts,
        'languages': languages,
        'language_guidance': language_guidance,
        'follow_up_questions': follow_up_toggle,
        'extra_questions': extra_questions,  # Add extra questions block
        'mode': 'followup'      # or "listener" / "survey"
    })
    
    logger.info(f"Event '{event_name}' initialized with follow-up and extra questions.")


# Define event details and survey questions
if __name__ == "__main__":
    event_id = "MultiLanFollowupMode2025Demo"
    event_name = "MultiLanFollow-up Mode2025 Demo"
    main_question = "What could make you change your mind about who you would vote for?"
    event_location = "Global"
    event_background = "A nationwide discussion on what could influence voters' decisions in upcoming elections."
    event_date = "2025"
   
    bot_topic = "Experiences and challenges of LBQ+ women in the workplace and community"
    bot_aim = "Encourage users to reflect on factors that could influence their voting decisions."
    bot_principles = [
        "Avoid repeating user responses verbatim. Instead, acknowledge their input with concise and meaningful replies, such as 'Thank you for your input' or similar",
        "Respect privacy and confidentiality",
        "Encourage honest and thoughtful responses"
    ]
    bot_personality = "Empathetic, supportive, and respectful"
    bot_additional_prompts = [
        "What are some unique challenges you face?",
        "How can your workplace better support LBQ+ individuals?"
    ]
    languages = ["English", "French", "Swahili"]
    #added
    language_guidance = "The bot should prioritize matching the user's language when detected, but default to English if unclear. Avoid switching languages mid-conversation."

    initial_message = (
        "Thank you for agreeing to participate. We want to assure you that none of the data you provide will be directly linked back to you. "
        "Your identity is protected through secure and encrypted links."
    )

    completion_message = (
        "Thank you for sharing your thoughts; it's been insightful exploring what influences your voting decisions. "
        "If there's anything else you'd like to discuss or reflect on, feel free to ask, or we can end the session here."
    )

    initialize_event_collection(
        event_id,
        event_name,
        event_location,
        event_background,
        event_date,
        bot_topic,
        bot_aim,
        bot_principles,
        bot_personality,
        bot_additional_prompts,
        main_question,
        languages,
        language_guidance,
        initial_message,
        completion_message,
    )

