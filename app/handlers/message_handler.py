# # app/handlers/message_handler.py
# import io
# from datetime import datetime, timedelta
# import requests
# from requests.auth import HTTPBasicAuth
# from fastapi import Response
# import logging

# from app.services import firestore_service, twilio_service, openai_service
# from app.utils import helpers
# from app.utils.validators import is_valid_name

# logger = logging.getLogger(__name__)

# async def process_message(Body: str, From: str, MediaUrl0: str = None) -> Response:
#     logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

#     # Normalize phone number
#     normalized_phone = From.replace("+", "").replace("-", "").replace(" ", "")

#     # --- Step 1: Retrieve or initialize user tracking document ---
#     user_tracking_ref, user_data = firestore_service.get_or_create_user(normalized_phone)
#     user_events = user_data.get('events', [])
#     current_event_id = user_data.get('current_event_id')
#     awaiting_event_id = user_data.get('awaiting_event_id', False)
#     awaiting_event_change_confirmation = user_data.get('awaiting_event_change_confirmation', False)
#     last_inactivity_prompt = user_data.get('last_inactivity_prompt')
#     awaiting_extra_questions = user_data.get('awaiting_extra_questions', False)
#     current_extra_question_index = user_data.get('current_extra_question_index', 0)
#     invalid_attempts = user_data.get('invalid_attempts', 0)

#     # Remove duplicate events and update tracking
#     user_events = helpers.remove_duplicate_events(user_events)
#     firestore_service.update_user_events(normalized_phone, user_events)

#     # --- Step 2: Validate current event ---
#     if current_event_id:
#         if not firestore_service.event_exists(current_event_id):
#             user_events = [e for e in user_events if e['event_id'] != current_event_id]
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'current_event_id': None,
#                 'events': user_events,
#                 'awaiting_event_id': True
#             })
#             twilio_service.send_message(From, f"The event '{current_event_id}' is no longer active. Please enter a new event ID to continue.")
#             return Response(status_code=200)

#     # --- Step 3: Handle inactivity (24h check) ---
#     current_time = datetime.utcnow()
#     if helpers.check_inactivity(user_events, current_time):
#         if not last_inactivity_prompt or helpers.can_prompt_again(last_inactivity_prompt, current_time):
#             event_list = helpers.format_event_list(user_events)
#             twilio_service.send_message(From, f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
#             firestore_service.update_user_tracking(normalized_phone, {'last_inactivity_prompt': current_time.isoformat()})
#             return Response(status_code=200)

#     # --- Step 4: If awaiting event selection after inactivity ---
#     if last_inactivity_prompt:
#         if Body.isdigit() and 1 <= int(Body) <= len(user_events):
#             selected_event = user_events[int(Body) - 1]['event_id']
#             twilio_service.send_message(From, f"You are now continuing in event {selected_event}.")
#             current_event_id = selected_event
#             user_events = helpers.update_event_timestamp(user_events, selected_event, current_time)
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'current_event_id': current_event_id,
#                 'events': user_events,
#                 'last_inactivity_prompt': None,
#                 'invalid_attempts': 0
#             })
#             return Response(status_code=200)
#         else:
#             invalid_attempts += 1
#             if invalid_attempts < 2:
#                 firestore_service.update_user_tracking(normalized_phone, {'invalid_attempts': invalid_attempts})
#                 twilio_service.send_message(From, "Invalid event selection. Please reply with the number corresponding to the event you'd like to continue.")
#                 return Response(status_code=200)
#             else:
#                 if current_event_id:
#                     twilio_service.send_message(From, f"No valid selection made. Continuing with your current event '{current_event_id}'.")
#                     user_events = helpers.update_event_timestamp(user_events, current_event_id, current_time)
#                     firestore_service.update_user_tracking(normalized_phone, {
#                         'current_event_id': current_event_id,
#                         'events': user_events,
#                         'last_inactivity_prompt': None,
#                         'invalid_attempts': 0
#                     })
#                     return Response(status_code=200)
#                 else:
#                     twilio_service.send_message(From, "No valid selection made and no current event found. Please provide your event ID to proceed.")
#                     firestore_service.update_user_tracking(normalized_phone, {
#                         'awaiting_event_id': True,
#                         'last_inactivity_prompt': None,
#                         'invalid_attempts': 0
#                     })
#                     return Response(status_code=200)

#     # --- Step 5: Handle event change confirmation ---
#     if awaiting_event_change_confirmation:
#         if Body.strip().lower() in ['yes', 'y']:
#             new_event_id = user_data.get('new_event_id_pending')
#             if not firestore_service.validate_event_id(new_event_id):
#                 twilio_service.send_message(From, f"The event ID '{new_event_id}' is no longer valid. Please enter a new event ID.")
#                 firestore_service.update_user_tracking(normalized_phone, {
#                     'awaiting_event_change_confirmation': False,
#                     'new_event_id_pending': None,
#                     'awaiting_event_id': True
#                 })
#                 return Response(status_code=200)
#             current_event_id = new_event_id
#             user_events = helpers.update_event_timestamp(user_events, current_event_id, current_time, add_if_missing=True)
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'current_event_id': current_event_id,
#                 'events': user_events,
#                 'awaiting_event_change_confirmation': False,
#                 'new_event_id_pending': None,
#                 'awaiting_extra_questions': False,
#                 'current_extra_question_index': 0
#             })
#             firestore_service.initialize_event_for_user(current_event_id, normalized_phone)
#             initial_message = firestore_service.get_initial_message(current_event_id)
#             twilio_service.send_message(From, f"You have switched to event {current_event_id}.")
#             # Start extra questions flow if applicable
#             if firestore_service.event_has_extra_questions(current_event_id):
#                 extra_questions, ordered_keys = firestore_service.get_ordered_extra_questions(current_event_id)
#                 if ordered_keys:
#                     firestore_service.update_user_tracking(normalized_phone, {
#                         'awaiting_extra_questions': True,
#                         'current_extra_question_index': 0
#                     })
#                     first_question_text = extra_questions[ordered_keys[0]]['text']
#                     combined_msg = f"{initial_message}\n\n{first_question_text}"
#                     twilio_service.send_message(From, combined_msg)
#             return Response(status_code=200)
#         else:
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'awaiting_event_change_confirmation': False,
#                 'new_event_id_pending': None
#             })
#             twilio_service.send_message(From, f"Event change cancelled. You remain in event {current_event_id}. Please continue.")
#             return Response(status_code=200)

#     # --- Step 6: Awaiting a brand new event ID ---
#     if awaiting_event_id:
#         extracted_event_id = openai_service.extract_event_id_with_llm(Body)
#         if extracted_event_id and firestore_service.validate_event_id(extracted_event_id):
#             current_event_id = extracted_event_id
#             user_events = helpers.update_event_timestamp(user_events, current_event_id, current_time, add_if_missing=True)
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'events': user_events,
#                 'current_event_id': current_event_id,
#                 'awaiting_event_id': False,
#                 'awaiting_extra_questions': False,
#                 'current_extra_question_index': 0
#             })
#             firestore_service.initialize_event_for_user(current_event_id, normalized_phone)
#             initial_message = firestore_service.get_initial_message(current_event_id)
#             if firestore_service.event_has_extra_questions(current_event_id):
#                 extra_questions, ordered_keys = firestore_service.get_ordered_extra_questions(current_event_id)
#                 if ordered_keys:
#                     firestore_service.update_user_tracking(normalized_phone, {
#                         'awaiting_extra_questions': True,
#                         'current_extra_question_index': 0
#                     })
#                     first_question_text = extra_questions[ordered_keys[0]]['text']
#                     combined_msg = f"{initial_message}\n\n{first_question_text}"
#                     twilio_service.send_message(From, combined_msg)
#             else:
#                 participant_data = firestore_service.get_event_user_data(current_event_id, normalized_phone)
#                 welcome_msg = openai_service.create_welcome_message(current_event_id, participant_data.get('name'))
#                 twilio_service.send_message(From, welcome_msg)
#             return Response(status_code=200)
#         else:
#             twilio_service.send_message(From, "The event ID you provided is invalid. Please re-enter the correct event ID or contact support.")
#             return Response(status_code=200)

#     # --- Step 7: Handle extra questions mode ---
#     if awaiting_extra_questions and current_event_id:
#         if MediaUrl0:
#             content_type, audio_text = twilio_service.transcribe_media(MediaUrl0)
#             if content_type and 'audio' in content_type:
#                 Body = audio_text
#             else:
#                 return Response(status_code=400, content="Unsupported media type.")
#         extra_questions, ordered_keys = firestore_service.get_ordered_extra_questions(current_event_id)
#         participant_data = firestore_service.get_event_user_data(current_event_id, normalized_phone)
#         if current_extra_question_index < len(ordered_keys):
#             question_key = ordered_keys[current_extra_question_index]
#             question_info = extra_questions[question_key]
#             function_id = question_info.get('id')
#             if function_id == "extract_name_with_llm":
#                 name_val = openai_service.extract_name_with_llm(Body, current_event_id)
#                 firestore_service.update_event_user_field(current_event_id, normalized_phone, {question_key: name_val, "name": name_val})
#             elif function_id == "extract_age_with_llm":
#                 age_val = openai_service.extract_age_with_llm(Body, current_event_id)
#                 firestore_service.update_event_user_field(current_event_id, normalized_phone, {question_key: age_val})
#             elif function_id == "extract_gender_with_llm":
#                 gender_val = openai_service.extract_gender_with_llm(Body, current_event_id)
#                 firestore_service.update_event_user_field(current_event_id, normalized_phone, {question_key: gender_val})
#             elif function_id == "extract_region_with_llm":
#                 region_val = openai_service.extract_region_with_llm(Body, current_event_id)
#                 firestore_service.update_event_user_field(current_event_id, normalized_phone, {question_key: region_val})
#             else:
#                 firestore_service.update_event_user_field(current_event_id, normalized_phone, {question_key: Body})
#             current_extra_question_index += 1
#             firestore_service.update_user_tracking(normalized_phone, {'current_extra_question_index': current_extra_question_index})
#             if current_extra_question_index < len(ordered_keys):
#                 next_question_text = extra_questions[ordered_keys[current_extra_question_index]]['text']
#                 twilio_service.send_message(From, next_question_text)
#             else:
#                 firestore_service.update_user_tracking(normalized_phone, {'awaiting_extra_questions': False})
#                 updated_data = firestore_service.get_event_user_data(current_event_id, normalized_phone)
#                 participant_name = updated_data.get('name')
#                 welcome_msg = openai_service.create_welcome_message(current_event_id, participant_name)
#                 twilio_service.send_message(From, welcome_msg)
#         return Response(status_code=200)

#     # --- Step 8: If no current event ID, try to extract one ---
#     if not current_event_id:
#         extracted_event_id = openai_service.extract_event_id_with_llm(Body)
#         if extracted_event_id and firestore_service.validate_event_id(extracted_event_id):
#             current_event_id = extracted_event_id
#             user_events = helpers.update_event_timestamp(user_events, current_event_id, current_time, add_if_missing=True)
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'events': user_events,
#                 'current_event_id': current_event_id,
#                 'awaiting_event_id': False,
#                 'awaiting_extra_questions': False,
#                 'current_extra_question_index': 0
#             })
#             firestore_service.initialize_event_for_user(current_event_id, normalized_phone)
#             initial_message = firestore_service.get_initial_message(current_event_id)
#             twilio_service.send_message(From, initial_message)
#             if firestore_service.event_has_extra_questions(current_event_id):
#                 extra_questions, ordered_keys = firestore_service.get_ordered_extra_questions(current_event_id)
#                 if ordered_keys:
#                     firestore_service.update_user_tracking(normalized_phone, {
#                         'awaiting_extra_questions': True,
#                         'current_extra_question_index': 0
#                     })
#                     first_text = extra_questions[ordered_keys[0]]['text']
#                     twilio_service.send_message(From, first_text)
#                 else:
#                     participant_data = firestore_service.get_event_user_data(current_event_id, normalized_phone)
#                     welcome_msg = openai_service.create_welcome_message(current_event_id, participant_data.get('name'))
#                     twilio_service.send_message(From, welcome_msg)
#             else:
#                 participant_data = firestore_service.get_event_user_data(current_event_id, normalized_phone)
#                 welcome_msg = openai_service.create_welcome_message(current_event_id, participant_data.get('name'))
#                 twilio_service.send_message(From, welcome_msg)
#             return Response(status_code=200)
#         else:
#             twilio_service.send_message(From, "Welcome! Please provide your event ID to proceed.")
#             firestore_service.update_user_tracking(normalized_phone, {'awaiting_event_id': True})
#             return Response(status_code=200)

#     # --- Step 9: Handle "change name" or "change event" commands ---
#     if Body.lower().startswith("change name "):
#         new_name = Body[12:].strip()
#         if new_name:
#             firestore_service.update_event_user_field(current_event_id, normalized_phone, {"name": new_name})
#             twilio_service.send_message(From, f"Your name has been updated to {new_name}. Please continue.")
#         else:
#             twilio_service.send_message(From, "It seems there was an error updating your name. Please try again.")
#         return Response(status_code=200)
#     elif Body.lower().startswith("change event "):
#         new_event_id = Body[13:].strip()
#         if firestore_service.validate_event_id(new_event_id):
#             if new_event_id == current_event_id:
#                 twilio_service.send_message(From, f"You are already in event {new_event_id}.")
#                 return Response(status_code=200)
#             twilio_service.send_message(From, f"You requested to change to event {new_event_id}. Please confirm by replying 'yes' or cancel with 'no'.")
#             firestore_service.update_user_tracking(normalized_phone, {
#                 'awaiting_event_change_confirmation': True,
#                 'new_event_id_pending': new_event_id
#             })
#         else:
#             twilio_service.send_message(From, f"The event ID '{new_event_id}' is invalid. Please check and try again.")
#         return Response(status_code=200)

#     # --- Step 10: Handle finalizing conversation ---
#     if Body.strip().lower() in ['finalize', 'finish']:
#         completion_message = firestore_service.get_completion_message(current_event_id)
#         twilio_service.send_message(From, completion_message)
#         return Response(status_code=200)

#     # --- Step 11: Otherwise, normal conversation via LLM ---
#     event_instructions = openai_service.generate_bot_instructions(current_event_id)
#     if MediaUrl0:
#         content_type, audio_text = twilio_service.transcribe_media(MediaUrl0)
#         if content_type and 'audio' in content_type:
#             Body = audio_text
#         else:
#             return Response(status_code=400, content="Unsupported media type.")
#     if not Body:
#         return Response(status_code=400)
    
#     # Save user message as an interaction
#     firestore_service.append_event_interaction(current_event_id, normalized_phone, {'message': Body})
    
#     # Create a thread and process the message via OpenAI
#     thread_id = openai_service.create_thread()
#     openai_service.send_user_message(thread_id, Body)
#     run = openai_service.create_and_poll_run(thread_id, event_instructions)
#     if run.get("status") == "completed":
#         messages = openai_service.list_thread_messages(thread_id)
#         assistant_response = openai_service.extract_text_from_messages(messages)
#         twilio_service.send_message(From, assistant_response)
#         firestore_service.append_event_interaction(current_event_id, normalized_phone, {'response': assistant_response})
#     else:
#         twilio_service.send_message(From, "There was an issue processing your request.")

#     return Response(status_code=200)





import logging
import json
import os
import io
import re
from uuid import uuid4
from datetime import datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth
from pydub import AudioSegment
from fastapi import Response

from config.config import (
    db, logger, client, twilio_client,
    twilio_number, assistant_id,
    twilio_account_sid, twilio_auth_token
)
from app.utils.validators import is_valid_name
from app.utils.helpers import generate_bot_instructions
from app.services.twilio_service import send_message
from app.services.openai_service import (
    extract_text_from_messages,
    extract_name_with_llm,
    extract_event_id_with_llm,
    event_id_valid,
    create_welcome_message,
    extract_age_with_llm,
    extract_gender_with_llm,
    extract_region_with_llm
)

async def reply(Body: str, From: str, MediaUrl0: str = None):
    logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

    # Normalize phone number
    normalized_phone = From.replace("+", "").replace("-", "").replace(" ", "")

    # Step 1: Retrieve or initialize user tracking document
    user_tracking_ref = db.collection('user_event_tracking').document(normalized_phone)
    user_tracking_doc = user_tracking_ref.get()
    if user_tracking_doc.exists:
        user_data = user_tracking_doc.to_dict()
    else:
        user_data = {
            'events': [], 'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        user_tracking_ref.set(user_data)

    # Extract fields
    user_events = user_data.get('events', [])
    current_event_id = user_data.get('current_event_id')
    awaiting_event_id = user_data.get('awaiting_event_id', False)
    awaiting_event_change_confirmation = user_data.get('awaiting_event_change_confirmation', False)
    last_inactivity_prompt = user_data.get('last_inactivity_prompt', None)
    awaiting_extra_questions = user_data.get('awaiting_extra_questions', False)
    current_extra_question_index = user_data.get('current_extra_question_index', 0)
    invalid_attempts = user_data.get('invalid_attempts', 0)

    # Remove duplicate events, keep latest
    unique_events = {}
    for event in user_events:
        eid = event['event_id']
        if eid not in unique_events:
            unique_events[eid] = event
        else:
            existing_time = datetime.fromisoformat(unique_events[eid]['timestamp'])
            new_time = datetime.fromisoformat(event['timestamp'])
            if new_time > existing_time:
                unique_events[eid] = event
    user_events = list(unique_events.values())
    user_data['events'] = user_events
    user_tracking_ref.update({'events': user_events})

    # Validate current event exists
    if current_event_id:
        event_info_ref = db.collection(f'AOI_{current_event_id}').document('info')
        if not event_info_ref.get().exists:
            user_events = [e for e in user_events if e['event_id'] != current_event_id]
            user_tracking_ref.update({
                'current_event_id': None,
                'events': user_events,
                'awaiting_event_id': True
            })
            send_message(From, f"The event '{current_event_id}' is no longer active. Please enter a new event ID to continue.")
            return Response(status_code=200)

    # Step 2: Inactivity check (24h)
    current_time = datetime.utcnow()
    user_inactive = False

    if user_events:
        last_times = []
        for evt in user_events:
            ts = evt.get('timestamp')
            if ts:
                last_times.append(datetime.fromisoformat(ts))
        if last_times:
            most_recent = max(last_times)
            if current_time - most_recent > timedelta(hours=24):
                user_inactive = True

    if user_inactive:
        if last_inactivity_prompt:
            last_prompt_time = datetime.fromisoformat(last_inactivity_prompt)
            if current_time - last_prompt_time >= timedelta(hours=24):
                event_list = '\n'.join(f"{i+1}. {e['event_id']}" for i,e in enumerate(user_events))
                send_message(From, f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
                user_tracking_ref.update({'last_inactivity_prompt': current_time.isoformat()})
                return Response(status_code=200)
        else:
            event_list = '\n'.join(f"{i+1}. {e['event_id']}" for i,e in enumerate(user_events))
            send_message(From, f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
            user_tracking_ref.update({'last_inactivity_prompt': current_time.isoformat()})
            return Response(status_code=200)

    # Step 3: Handle inactivity-selection response
    if last_inactivity_prompt:
        if Body.isdigit() and 1 <= int(Body) <= len(user_events):
            selected_event = user_events[int(Body)-1]['event_id']
            send_message(From, f"You are now continuing in event {selected_event}.")
            current_event_id = selected_event
            now_iso = datetime.utcnow().isoformat()
            for evt in user_events:
                if evt['event_id'] == selected_event:
                    evt['timestamp'] = now_iso
            user_tracking_ref.update({
                'current_event_id': current_event_id,
                'events': user_events,
                'last_inactivity_prompt': None,
                'invalid_attempts': 0
            })
            return Response(status_code=200)
        else:
            invalid_attempts += 1
            if invalid_attempts < 2:
                user_tracking_ref.update({'invalid_attempts': invalid_attempts})
                send_message(From, "Invalid event selection. Please reply with the number corresponding to the event you'd like to continue.")
                return Response(status_code=200)
            else:
                if current_event_id:
                    send_message(From, f"No valid selection made. Continuing with your current event '{current_event_id}'.")
                    now_iso = datetime.utcnow().isoformat()
                    for evt in user_events:
                        if evt['event_id'] == current_event_id:
                            evt['timestamp'] = now_iso
                    user_tracking_ref.update({
                        'current_event_id': current_event_id,
                        'events': user_events,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)
                else:
                    send_message(From, "No valid selection made and no current event found. Please provide your event ID to proceed.")
                    user_tracking_ref.update({
                        'awaiting_event_id': True,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)

    # Step 4: Confirm event change
    if awaiting_event_change_confirmation:
        if Body.strip().lower() in ['yes','y']:
            new_event_id = user_data.get('new_event_id_pending')
            if not event_id_valid(new_event_id):
                send_message(From, f"The event ID '{new_event_id}' is no longer valid. Please enter a new event ID.")
                user_tracking_ref.update({
                    'awaiting_event_change_confirmation': False,
                    'new_event_id_pending': None,
                    'awaiting_event_id': True
                })
                return Response(status_code=200)

            # switch
            current_event_id = new_event_id
            now_iso = datetime.utcnow().isoformat()
            exists=False
            for evt in user_events:
                if evt['event_id']==current_event_id:
                    evt['timestamp']=now_iso
                    exists=True
            if not exists:
                user_events.append({'event_id':current_event_id,'timestamp':now_iso})

            user_tracking_ref.update({
                'current_event_id': current_event_id,
                'events': user_events,
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })

            # init participant doc
            event_doc_ref = db.collection(f'AOI_{current_event_id}').document(normalized_phone)
            if not event_doc_ref.get().exists:
                event_doc_ref.set({'name':None,'interactions':[],'event_id':current_event_id})

            send_message(From, f"You have switched to event {current_event_id}.")
            # ... [rest of extra-question flow unchanged]
            return Response(status_code=200)
        else:
            user_tracking_ref.update({
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None
            })
            send_message(From, f"Event change cancelled. You remain in event {current_event_id}. Please continue.")
            return Response(status_code=200)

    # Step 5: New event ID flow
    if awaiting_event_id:
        extracted_event_id = extract_event_id_with_llm(Body)
        if extracted_event_id and event_id_valid(extracted_event_id):
            event_id = extracted_event_id
            current_event_id = event_id
            now_iso = datetime.utcnow().isoformat()

            found=False
            for evt in user_events:
                if evt['event_id']==event_id:
                    evt['timestamp']=now_iso
                    found=True
            if not found:
                user_events.append({'event_id':event_id,'timestamp':now_iso})

            user_tracking_ref.update({
                'events': user_events,
                'current_event_id': current_event_id,
                'awaiting_event_id': False,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })

            db.collection(f'AOI_{event_id}').document(normalized_phone).set({'name':None,'interactions':[],'event_id':event_id})
            # ... [send initial + extra-questions or welcome exactly as before]
            return Response(status_code=200)
        else:
            logger.info(f"Invalid event ID: {Body}")
            send_message(From, "The event ID you provided is invalid. Please re-enter the correct event ID or contact support.")
            return Response(status_code=200)

    # Step 6: Extra questions flow
    if awaiting_extra_questions and current_event_id:
        # [transcription + question loop exactly as before]
        return Response(status_code=200)

    # Step 7: No current event
    if not current_event_id:
        extracted_event_id = extract_event_id_with_llm(Body)
        if extracted_event_id and event_id_valid(extracted_event_id):
            # [same as Step 5 but with send_message(initial_message)]
            return Response(status_code=200)
        else:
            send_message(From, "Welcome! Please provide your event ID to proceed.")
            user_tracking_ref.update({'awaiting_event_id': True})
            return Response(status_code=200)

    # Step 8: change name / change event commands
    if Body.lower().startswith("change name "):
        new_name = Body[12:].strip()
        if new_name:
            db.collection(f'AOI_{current_event_id}').document(normalized_phone).update({'name': new_name})
            send_message(From, f"Your name has been updated to {new_name}. Please continue.")
        else:
            send_message(From, "It seems there was an error updating your name. Please try again.")
        return Response(status_code=200)
    elif Body.lower().startswith("change event "):
        new_event_id = Body[13:].strip()
        if event_id_valid(new_event_id):
            if new_event_id == current_event_id:
                send_message(From, f"You are already in event {new_event_id}.")
                return Response(status_code=200)
            send_message(From, f"You requested to change to event {new_event_id}. Please confirm by replying 'yes' or cancel with 'no'.")
            user_tracking_ref.update({
                'awaiting_event_change_confirmation': True,
                'new_event_id_pending': new_event_id
            })
        else:
            send_message(From, f"The event ID '{new_event_id}' is invalid. Please check and try again.")
        return Response(status_code=200)

    # Step 9: finalize
    if Body.strip().lower() in ['finalize','finish']:
        default_completion = "Thank you. You have completed this survey!"
        event_info_doc = db.collection(f'AOI_{current_event_id}').document('info').get()
        if event_info_doc.exists:
            cm = event_info_doc.to_dict().get('completion_message', default_completion)
        else:
            cm = default_completion
        send_message(From, cm)
        return Response(status_code=200)

    # Step 10: normal conversation
    event_info_doc = db.collection(f'AOI_{current_event_id}').document('info').get()
    welcome_message = "Welcome! You can now start sending text and audio messages."
    if event_info_doc.exists:
        welcome_message = event_info_doc.to_dict().get('welcome_message', welcome_message)

    instructions = generate_bot_instructions(current_event_id)

    # [handle media transcription exactly as before]
    # [LLM thread creation, run, response extraction, send_message, store in Firestore]
    return Response(status_code=200)
