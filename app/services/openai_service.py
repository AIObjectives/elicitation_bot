
from config.config import client, logger,db



# def extract_text_from_messages(messages):
#     # placeholder for your logic
#     from agent_functions2 import extract_text_from_messages as _fn
#     return _fn(messages)

# def extract_event_id_with_llm(text):
#     from agent_functions2 import extract_event_id_with_llm as _fn
#     return _fn(text)

# def extract_name_with_llm(text, event_id):
#     from agent_functions2 import extract_name_with_llm as _fn
#     return _fn(text, event_id)

# def event_id_valid(event_id):
#     from agent_functions2 import event_id_valid as _fn
#     return _fn(event_id)

# def create_welcome_message(event_id, participant_name=None):
#     from agent_functions2 import create_welcome_message as _fn
#     return _fn(event_id, participant_name)

# def extract_age_with_llm(text, event_id):
#     from agent_functions2 import extract_age_with_llm as _fn
#     return _fn(text, event_id)

# def extract_gender_with_llm(text, event_id):
#     from agent_functions2 import extract_gender_with_llm as _fn
#     return _fn(text, event_id)

# def extract_region_with_llm(text, event_id):
#     from agent_functions2 import extract_region_with_llm as _fn
#     return _fn(text, event_id)




#####



def is_valid_name(name):
    if not name:
        return False
    name = name.strip().strip('"').strip("'")
    if not name or name.lower() == "anonymous":
        return False
    # Check if name contains at least one alphabetic character
    if any(char.isalpha() for char in name):
        return True
    return False

def extract_text_from_messages(messages):
    texts = []
    for message in messages:
        # Check if the message role is 'assistant' before processing
        if message.role == 'assistant':
            for content_block in message.content:
                if hasattr(content_block, 'text') and hasattr(content_block.text, 'value'):
                    texts.append(content_block.text.value)
    return " ".join(texts)




def extract_event_id_with_llm(user_input):
    """Extract the event ID from the user's input using LLM analysis."""
    #from multiconf3_3 import db, client, logger
    # Fetch all valid event IDs from Firestore
    try:
        collections = db.collections()
        valid_event_ids = [collection.id.replace('AOI_', '') for collection in collections if collection.id.startswith('AOI_')]
    except Exception as e:
        logger.error(f"Error fetching event IDs: {e}")
        return None

    # Prepare the system message for LLM
    system_message = f"""
    You are to extract the event ID from the user's input. The event ID is one of the following IDs:
    {', '.join(valid_event_ids)}.

    The user's input may contain additional text. Your task is to identify and extract the event ID from the input.

    Return only the event ID. If you cannot find an event ID in the user's input, return 'No event ID found'.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ],
            max_tokens=20,
            temperature=0.2
        )
        if response.choices and response.choices[0].message.content.strip():
            event_id = response.choices[0].message.content.strip()
            print("this is the extracted",event_id)
            if event_id == "No event ID found":
                return None
            else:
                return event_id
        else:
            return None
    except Exception as e:
        logger.error(f"Error extracting event ID with LLM: {e}")
        return None
    


def extract_name_with_llm(user_input, event_id):
    """Extract the user's name from the user's input using LLM analysis."""
    # Fetch dynamic event-specific details from Firestore
    event_info_ref = db.collection(f'AOI_{event_id}').document('info')
    event_info_doc = event_info_ref.get()

    event_name = 'the event'
    event_location = 'the location'
    if event_info_doc.exists:
        event_info = event_info_doc.to_dict()
        event_name = event_info.get('event_name', event_name)
        event_location = event_info.get('event_location', event_location)

   
    system_message = f"""
    You are to extract the participant's name from the user's input. The user is participating in {event_name} in {event_location}.

    Instructions:
    - The user's input may contain their name or a statement that they prefer to remain anonymous.
    - If the user provides their name, extract only the name.
    - If the user indicates they prefer to remain anonymous, return "Anonymous".
    - If you cannot find a name in the user's input, return an empty string.

    Examples:
    - User Input: "My name is John." => Output: "John"
    - User Input: "I prefer not to share my name." => Output: "Anonymous"
    - User Input: "Anonymous" => Output: "Anonymous"
    - User Input: "Just call me Jane Doe." => Output: "Jane Doe"
    - User Input: "Hello!" => Output: ""
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ],
            max_tokens=50,
            temperature=0.6
        )

  

        if response.choices and response.choices[0].message.content.strip():
            name = response.choices[0].message.content.strip()
            # Remove surrounding quotes and whitespace
            name = name.strip().strip('"').strip("'")
            if not name or name.lower() in ["", "none"]:
                return None  # Return None if the name is empty or "none"
            else:
                return name
        else:
            return None  # Return None if no response
    except Exception as e:
        logger.error(f"Error in extracting name with LLM: {e}")
        return None
    


def event_id_valid(event_id):
    """ Validate event ID by checking if it exists in Firestore """
    #from multiconf3_3 import db, logger
    try:
        # Query Firestore for all collections starting with 'AOI_'
        collections = db.collections()
        valid_event_ids = [collection.id.replace('AOI_', '') for collection in collections if collection.id.startswith('AOI_')]

        # Check if the provided event_id exists in the list
        return event_id in valid_event_ids
    except Exception as e:
        logger.error(f"Error validating event ID: {e}")
        return False
    
def create_welcome_message(event_id, participant_name=None, prompt_for_name=False):
    """Construct the welcome message using the event's welcome_message from the database."""
    # Fetch event details
    event_info_ref = db.collection(f'AOI_{event_id}').document('info')
    event_info_doc = event_info_ref.get()
    welcome_message = "Welcome! You can now start sending text and audio messages."

    if event_info_doc.exists:
        event_info = event_info_doc.to_dict()
        welcome_message = event_info.get('welcome_message', welcome_message)

    # If participant_name is provided and not 'Anonymous', insert it into the welcome message
    #if participant_name and participant_name != "Anonymous":
    if is_valid_name(participant_name):

        # Attempt to insert the name into the welcome message
        if "Welcome to" in welcome_message:
            personalized_welcome = welcome_message.replace("Welcome to", f"Welcome {participant_name} to")
        else:
            # If "Welcome to" is not in the welcome message, prepend "Welcome {name}, " to the message
            personalized_welcome = f"Welcome {participant_name}, {welcome_message}"
    else:
        # Use the welcome message as is
        personalized_welcome = welcome_message

    # If we need to prompt for the name
    if prompt_for_name:
        # Append "Please tell me your name." to the message
        personalized_welcome += " Please tell me your name."

    return personalized_welcome




def extract_age_with_llm(user_input, current_event_id):
    """Extract the participant's age from the user's input using LLM analysis."""
    # Prepare the system message for LLM
    system_message = """
    You are to extract the participant's age from the user's input. The age should be an integer representing the person's age in years.

    The user's input may contain additional text. Your task is to identify and extract the age from the input.

    Return only the age as a number. If you cannot find an age in the user's input, return 'No age found'.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ],
            max_tokens=50,
            temperature=0.3
        )
        if response.choices and response.choices[0].message.content.strip():
            age = response.choices[0].message.content.strip()
            if age == "No age found":
                return "No age found"
            else:
                return age
        else:
            return "No age found"
    except Exception as e:
        logger.error(f"Error extracting age with LLM: {e}")
        return "No age found"






def extract_gender_with_llm(user_input, current_event_id):
    """Extract the participant's gender from the user's input using LLM analysis."""
    # Prepare the system message for LLM
    system_message = """
    You are to extract the participant's gender from the user's input.

    The user's input may contain additional text. Your task is to identify and extract the gender from the input.

    Return only the gender. Acceptable responses are 'Male', 'Female', 'Non-binary', or 'Other'. If you cannot find a gender in the user's input, return 'No gender found'.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ],
            max_tokens=60,
            temperature=0.4
        )
        if response.choices and response.choices[0].message.content.strip():
            gender = response.choices[0].message.content.strip()
            if gender == "No gender found":
                return "No gender found"
            else:
                return gender
        else:
            return "No gender found"
    except Exception as e:
        logger.error(f"Error extracting gender with LLM: {e}")
        return "No gender found"




def extract_region_with_llm(user_input, current_event_id):
    """Extract the participant's region from the user's input using LLM analysis."""
    # Prepare the system message for LLM
    system_message = """
    You are to extract the participant's region or location from the user's input.

    The user's input may contain additional text. Your task is to identify and extract the region from the input.

    Return only the region or location. If you cannot find a region in the user's input, return 'No region found'.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_input}
            ],
            max_tokens=60,
            temperature=0.4
        )
        if response.choices and response.choices[0].message.content.strip():
            region = response.choices[0].message.content.strip()
            if region == "No region found":
                return "No region found"
            else:
                return region
        else:
            return "No region found"
    except Exception as e:
        logger.error(f"Error extracting region with LLM: {e}")
        return "No region found"