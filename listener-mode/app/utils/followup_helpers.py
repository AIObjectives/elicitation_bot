from datetime import datetime
from config.config import db



def generate_bot_instructions(event_id, normalized_phone):
    """
    Generate dynamic bot instructions based on event details and user interactions.
    Includes all follow-up questions in the instructions so the agent can pick one
    or come up with its own if none are relevant.
    """
    # 1. Fetch event details from Firestore
    event_info_ref = db.collection(f'AOI_{event_id}').document('info')
    event_info_doc = event_info_ref.get()

    if event_info_doc.exists:
        event_info = event_info_doc.to_dict()
        event_name = event_info.get('event_name', 'the event')
        event_location = event_info.get('event_location', 'the location')
        event_background = event_info.get('event_background', 'the background')
        bot_topic = event_info.get('bot_topic', '')
        bot_aim = event_info.get('bot_aim', '')
        bot_principles = event_info.get('bot_principles', [])
        bot_personality = event_info.get('bot_personality', '')
        bot_additional_prompts = event_info.get('bot_additional_prompts', [])

        # Retrieve toggle & question list
        follow_up_toggle = event_info.get('follow_up_questions', {})
        follow_up_enabled = follow_up_toggle.get('enabled', False)
        follow_up_list = follow_up_toggle.get('questions', [])
    else:
        # Default if event info is missing
        event_name = 'the event'
        event_location = 'the location'
        event_background = 'the background'
        bot_topic = ''
        bot_aim = ''
        bot_principles = []
        bot_personality = ''
        bot_additional_prompts = []

        follow_up_toggle = {}
        follow_up_enabled = False
        follow_up_list = []

    # 2. Fetch past interactions for context
    event_doc_ref = db.collection(f'AOI_{event_id}').document(normalized_phone)
    event_doc = event_doc_ref.get()
    if event_doc.exists:
        user_data = event_doc.to_dict()
        interactions = user_data.get('interactions', [])
        bot_questions = [interaction.get('response') for interaction in interactions if 'response' in interaction]
        user_messages = [interaction.get('message') for interaction in interactions if 'message' in interaction]

        # Compile the last ~30 interactions to show context
        past_interactions_text = ''
        for q, m in zip(bot_questions[-30:], user_messages[-30:]):
            past_interactions_text += f'Bot: {q}\nUser: {m}\n'
    else:
        past_interactions_text = ''

    # 3. Prepare text for principles & additional prompts
    bot_principles_text = '\n'.join(f'- {principle}' for principle in bot_principles)
    bot_additional_prompts_text = '\n'.join(f'- {prompt}' for prompt in bot_additional_prompts)

    # 4. Convert follow-up questions into a simple enumerated list to show in prompt
    if follow_up_enabled and follow_up_list:
        print("11111Follow-up questions enabled and list is not empty")
        follow_up_list_text = "\n".join(f"{idx+1}. {q}" for idx, q in enumerate(follow_up_list))
    else:
        follow_up_list_text = ""  # If toggle is off or list is empty, no list is provided
        print("NOT ACTIVEFALSEEE-11111Follow-up questions enabled and list is not empty")

    

    # 5. Instructions for the LLM to pick a follow-up question or create its own
    if follow_up_enabled and follow_up_list:
        follow_up_instructions = """
Below is a list of possible follow-up questions. 
Please read the user's last response, pick (or adapt) the question that best fits their context, 
and replace "X" with relevant keywords or content from the user's response. 

If none of these follow-up questions seem relevant, 
please create your own question or statement to deepen the conversation.

Possible Follow-up Questions:
""" + follow_up_list_text
    else:
        # If toggle is OFF or there's no list, revert to a single "default" approach
        follow_up_instructions = """
No specialized follow-up questions are enabled at this time. 
Use your own approach to continue the conversation in a thoughtful way.
"""

    # 6. Build final instructions
    instructions = f"""
You are an "Elicitation bot", designed to interact conversationally with individual users on WhatsApp, and help draw out their opinions towards the assigned topic. The conversation should be engaging, friendly, and sometimes humorous to keep the interaction light-hearted yet productive. You provide an experience that lets users feel better heard. You also encourage users to think from a wider perspective and help them revise their initial opinions by considering broader perspectives.

### Event Information
Event Name: {event_name}
Event Location: {event_location}
Event Background: {event_background}

### Topic, Bot Objective, Conversation Principles, and Bot Personality
- **Topic**: {bot_topic}
- **Aim**: {bot_aim}
- **Principles**:
{bot_principles_text}
- **Personality**: {bot_personality}

### Past User Interactions
{past_interactions_text}

### Additional Prompts
{bot_additional_prompts_text}

### Follow-Up Questions and Instructions
{follow_up_instructions}

### Conversation Management
- Be respectful and avoid sensitive topics unless they are part of the assigned topic.
- Do not provide personal opinions or biases.

### Final Notes
Your role is to facilitate a meaningful conversation that helps the user express their authentic opinions on {bot_topic}, while ensuring they feel heard and valued.
""".strip()

    return instructions

