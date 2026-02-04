# # app/utils/helpers.py
# from datetime import datetime, timedelta

# def remove_duplicate_events(events):
#     unique = {}
#     for event in events:
#         eid = event.get('event_id')
#         timestamp = event.get('timestamp')
#         if eid not in unique:
#             unique[eid] = event
#         else:
#             if timestamp and unique[eid].get('timestamp'):
#                 if datetime.fromisoformat(timestamp) > datetime.fromisoformat(unique[eid]['timestamp']):
#                     unique[eid] = event
#     return list(unique.values())

# def check_inactivity(events, current_time):
#     if events:
#         timestamps = []
#         for evt in events:
#             ts = evt.get('timestamp')
#             if ts:
#                 timestamps.append(datetime.fromisoformat(ts))
#         if timestamps:
#             most_recent = max(timestamps)
#             return (current_time - most_recent) > timedelta(hours=24)
#     return False

# def can_prompt_again(last_prompt_time, current_time):
#     if not last_prompt_time:
#         return True
#     last = datetime.fromisoformat(last_prompt_time)
#     return (current_time - last) >= timedelta(hours=24)

# def format_event_list(events):
#     return "\n".join([f"{i+1}. {e['event_id']}" for i, e in enumerate(events)])

# def update_event_timestamp(events, event_id, current_time, add_if_missing=False):
#     updated = False
#     for event in events:
#         if event.get('event_id') == event_id:
#             event['timestamp'] = current_time.isoformat()
#             updated = True
#             break
#     if not updated and add_if_missing:
#         events.append({'event_id': event_id, 'timestamp': current_time.isoformat()})
#     return events



#These functions above will be used in the upcoming refactoring stages —
# at the moment, they are not being actively used.


def generate_bot_instructions(event_id):
    """
    Generate dynamic bot instructions based on the event's name and location.
    (moved wholesale from your monolithic file)
    """
    from app.services.firestore_service import EventService

    event_info = EventService.get_event_info(event_id)

    if event_info:
        event_name = event_info.get('event_name', 'the event')
        event_location = event_info.get('event_location', 'the location')
        event_background = event_info.get('event_background', 'the background')
        language_guidance = event_info.get('language_guidance', '')
    else:
        event_name = 'the event'
        event_location = 'the location'
        event_background = 'the background'
        language_guidance = ''

    instructions = f"""
    Bot Objective
    The AI bot is primarily designed to listen and record discussions at the {event_name} in {event_location} with minimal interaction. Its responses are restricted to one or two sentences only, to maintain focus on the participants' discussions.

    Event Background
    {event_background}

    Language Behavior
    {language_guidance if language_guidance else "No specific language behavior was requested. The bot defaults to matching the user's language when possible."}


    Bot Personality
    The bot is programmed to be non-intrusive and neutral, offering no more than essential interaction required to acknowledge participants' inputs.

    Listening Mode
    Data Retention: The bot is in a passive listening mode, capturing important discussion points without actively participating.
    Minimal Responses: The bot remains largely silent, offering brief acknowledgments if directly addressed.

    
    Interaction Guidelines
    Ultra-Brief Responses: If the bot needs to respond, it will use no more than one to two sentences, strictly adhering to this rule to prevent engaging beyond necessary acknowledgment.
    Acknowledgments: For instance, if a participant makes a point or asks if the bot is recording, it might say, "Acknowledged," or, "Yes, I'm recording. or Please continue," 

    Conversation Management
    Directive Responses: On rare occasions where direction is required and appropriate, the bot will use concise prompts like "Please continue," or, "Could you clarify?"
    Passive Engagement: The bot uses minimal phrases like "Understood" or "Noted" with professional emojis to confirm its presence and listening status without adding substance to the conversation.

    Closure of Interaction
    Concluding Interaction: When a dialogue concludes or a user ends the interaction, the bot responds succinctly with, "Thank you for the discussion."

    Overall Management
    The bot ensures it does not interfere with or distract from the human-centric discussions at the {event_name} in {event_location}. Its primary role is to support by listening and only acknowledging when absolutely necessary, ensuring that all interactions remain brief and to the point.
    """
    return instructions


#Change Session/Event/Name: If the user would like to change their name or event during the session, the bot will respond with: 'To change your name, type "change name [new name]". To change your event, type "change event [event name]".'