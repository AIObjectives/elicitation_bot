# # app/services/openai_service.py
# import openai
# from config.config import OPENAI_API_KEY, OPENAI_ENGINE, ASSISTANT_ID, logger

# openai.api_key = OPENAI_API_KEY

# def extract_event_id_with_llm(user_input):
#     system_message = "Extract the event ID from the user input."
#     try:
#         response = openai.ChatCompletion.create(
#             model=OPENAI_ENGINE,
#             messages=[
#                 {"role": "system", "content": system_message},
#                 {"role": "user", "content": user_input}
#             ],
#             max_tokens=20,
#             temperature=0.2
#         )
#         content = response.choices[0].message.content.strip()
#         return None if content == "No event ID found" else content
#     except Exception as e:
#         logger.error(f"Error extracting event ID: {e}")
#         return None

# def extract_name_with_llm(user_input, event_id):
#     system_message = f"Extract the participant's name from the input for event {event_id}."
#     try:
#         response = openai.ChatCompletion.create(
#             model=OPENAI_ENGINE,
#             messages=[
#                 {"role": "system", "content": system_message},
#                 {"role": "user", "content": user_input}
#             ],
#             max_tokens=50,
#             temperature=0.6
#         )
#         name = response.choices[0].message.content.strip().strip('"').strip("'")
#         return None if not name or name.lower() in ["", "none"] else name
#     except Exception as e:
#         logger.error(f"Error extracting name: {e}")
#         return None

# def extract_age_with_llm(user_input, event_id):
#     system_message = "Extract the participant's age as an integer. Return 'No age found' if not present."
#     try:
#         response = openai.ChatCompletion.create(
#             model=OPENAI_ENGINE,
#             messages=[
#                 {"role": "system", "content": system_message},
#                 {"role": "user", "content": user_input}
#             ],
#             max_tokens=50,
#             temperature=0.3
#         )
#         age = response.choices[0].message.content.strip()
#         return age if age != "No age found" else "No age found"
#     except Exception as e:
#         logger.error(f"Error extracting age: {e}")
#         return "No age found"

# def extract_gender_with_llm(user_input, event_id):
#     system_message = "Extract the participant's gender. Accept 'Male', 'Female', 'Non-binary', or 'Other'. Return 'No gender found' if not present."
#     try:
#         response = openai.ChatCompletion.create(
#             model=OPENAI_ENGINE,
#             messages=[
#                 {"role": "system", "content": system_message},
#                 {"role": "user", "content": user_input}
#             ],
#             max_tokens=60,
#             temperature=0.4
#         )
#         gender = response.choices[0].message.content.strip()
#         return gender if gender != "No gender found" else "No gender found"
#     except Exception as e:
#         logger.error(f"Error extracting gender: {e}")
#         return "No gender found"

# def extract_region_with_llm(user_input, event_id):
#     system_message = "Extract the participant's region from the input. Return 'No region found' if not present."
#     try:
#         response = openai.ChatCompletion.create(
#             model=OPENAI_ENGINE,
#             messages=[
#                 {"role": "system", "content": system_message},
#                 {"role": "user", "content": user_input}
#             ],
#             max_tokens=60,
#             temperature=0.4
#         )
#         region = response.choices[0].message.content.strip()
#         return region if region != "No region found" else "No region found"
#     except Exception as e:
#         logger.error(f"Error extracting region: {e}")
#         return "No region found"

# def create_welcome_message(event_id, participant_name=None, prompt_for_name=False):
#     from app.services import firestore_service
#     initial_message = firestore_service.get_initial_message(event_id)
#     if participant_name:
#         welcome_msg = f"Welcome {participant_name}, {initial_message}"
#     else:
#         welcome_msg = initial_message
#     if prompt_for_name:
#         welcome_msg += " Please tell me your name."
#     return welcome_msg

# def generate_bot_instructions(event_id):
#     instructions = f"Bot instructions for event {event_id}. Please respond briefly."
#     return instructions

# # Simulated thread functions

# def create_thread():
#     return "thread_id_example"

# def send_user_message(thread_id, content):
#     # Simulate sending the user message to a thread
#     pass

# def create_and_poll_run(thread_id, instructions):
#     # Simulate polling a run until completion
#     return {"status": "completed"}

# def list_thread_messages(thread_id):
#     # Simulate returning messages from the thread
#     class Message:
#         def __init__(self, role, content):
#             self.role = role
#             self.message = type("msg", (), {"content": content})
#     return [Message("assistant", "Simulated assistant response.")]

# def extract_text_from_messages(messages):
#     texts = []
#     for msg in messages:
#         if msg.role == 'assistant':
#             texts.append(msg.message.content)
#     return " ".join(texts)






##

from config.config import client

def extract_text_from_messages(messages):
    # placeholder for your logic
    from agent_functions2 import extract_text_from_messages as _fn
    return _fn(messages)

def extract_event_id_with_llm(text):
    from agent_functions2 import extract_event_id_with_llm as _fn
    return _fn(text)

def extract_name_with_llm(text, event_id):
    from agent_functions2 import extract_name_with_llm as _fn
    return _fn(text, event_id)

def event_id_valid(event_id):
    from agent_functions2 import event_id_valid as _fn
    return _fn(event_id)

def create_welcome_message(event_id, participant_name=None):
    from agent_functions2 import create_welcome_message as _fn
    return _fn(event_id, participant_name)

def extract_age_with_llm(text, event_id):
    from agent_functions2 import extract_age_with_llm as _fn
    return _fn(text, event_id)

def extract_gender_with_llm(text, event_id):
    from agent_functions2 import extract_gender_with_llm as _fn
    return _fn(text, event_id)

def extract_region_with_llm(text, event_id):
    from agent_functions2 import extract_region_with_llm as _fn
    return _fn(text, event_id)
