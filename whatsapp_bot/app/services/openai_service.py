
from config.config import client, logger, db

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




def extract_event_id_with_llm(user_input):
    """Extract the event ID from the user's input using LLM analysis."""
    # Fetch all valid event IDs from Firestore (new schema: elicitation_bot_events)
    try:
        events = db.collection('elicitation_bot_events').stream()
        valid_event_ids = [event.id for event in events]
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
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=20,
            system=[{"type": "text", "text": system_message, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_input}],
        )
        event_id = response.content[0].text.strip()
        print("this is the extracted", event_id)
        if event_id == "No event ID found":
            return None
        return event_id
    except Exception as e:
        logger.error(f"Error extracting event ID with LLM: {e}")
        return None



def extract_name_with_llm(user_input, event_id):
    """Extract the user's name from the user's input using LLM analysis."""
    # Fetch dynamic event-specific details from Firestore (new schema: elicitation_bot_events/event_id)
    event_doc = db.collection('elicitation_bot_events').document(event_id).get()

    event_name = 'the event'
    event_location = 'the location'
    if event_doc.exists:
        event_info = event_doc.to_dict()
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
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=50,
            system=[{"type": "text", "text": system_message, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_input}],
        )
        name = response.content[0].text.strip().strip('"').strip("'")
        if not name or name.lower() in ["", "none"]:
            return None
        return name
    except Exception as e:
        logger.error(f"Error in extracting name with LLM: {e}")
        return None



def event_id_valid(event_id):
    """ Validate event ID by checking if it exists in Firestore """
    try:
        # Check if event exists in elicitation_bot_events collection
        event_doc = db.collection('elicitation_bot_events').document(event_id).get()
        return event_doc.exists
    except Exception as e:
        logger.error(f"Error validating event ID: {e}")
        return False

def create_welcome_message(event_id, participant_name=None, prompt_for_name=False):
    """Construct the welcome message using the event's welcome_message from the database."""
    # Fetch event details from new schema: elicitation_bot_events/event_id
    event_doc = db.collection('elicitation_bot_events').document(event_id).get()
    welcome_message = "Welcome! You can now start sending text and audio messages."

    if event_doc.exists:
        event_info = event_doc.to_dict()
        welcome_message = event_info.get('welcome_message', welcome_message)

    # If participant_name is provided and not 'Anonymous', insert it into the welcome message
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
    system_message = """
    You are to extract the participant's age from the user's input. The age should be an integer representing the person's age in years.

    The user's input may contain additional text. Your task is to identify and extract the age from the input.

    Return only the age as a number. If you cannot find an age in the user's input, return 'No age found'.
    """

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=50,
            system=[{"type": "text", "text": system_message, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_input}],
        )
        age = response.content[0].text.strip()
        if age == "No age found":
            return "No age found"
        return age
    except Exception as e:
        logger.error(f"Error extracting age with LLM: {e}")
        return "No age found"




def extract_gender_with_llm(user_input, current_event_id):
    """Extract the participant's gender from the user's input using LLM analysis."""
    system_message = """
    You are to extract the participant's gender from the user's input.

    The user's input may contain additional text. Your task is to identify and extract the gender from the input.

    Return only the gender. Acceptable responses are 'Male', 'Female', 'Non-binary', or 'Other'. If you cannot find a gender in the user's input, return 'No gender found'.
    """

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=60,
            system=[{"type": "text", "text": system_message, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_input}],
        )
        gender = response.content[0].text.strip()
        if gender == "No gender found":
            return "No gender found"
        return gender
    except Exception as e:
        logger.error(f"Error extracting gender with LLM: {e}")
        return "No gender found"




def extract_region_with_llm(user_input, current_event_id):
    """Extract the participant's region from the user's input using LLM analysis."""
    system_message = """
    You are to extract the participant's region or location from the user's input.

    The user's input may contain additional text. Your task is to identify and extract the region from the input.

    Return only the region or location. If you cannot find a region in the user's input, return 'No region found'.
    """

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=60,
            system=[{"type": "text", "text": system_message, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_input}],
        )
        region = response.content[0].text.strip()
        if region == "No region found":
            return "No region found"
        return region
    except Exception as e:
        logger.error(f"Error extracting region with LLM: {e}")
        return "No region found"
