
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
from app.services.firestore_service import (
    UserTrackingService,
    EventService,
    ParticipantService
)
from app.utils.survey_helpers import initialize_user_document
from app.utils.validators import normalize_event_path, normalize_phone
from app.utils.blocklist_helpers import get_interaction_limit, is_blocked_number


async def reply_survey(Body: str, From: str, MediaUrl0: str = None):
    logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

    normalized_phone = normalize_phone(From)
    if is_blocked_number(normalized_phone):
        logger.warning(f"[Blacklist] Ignoring message from blocked number: {normalized_phone}")
        return Response(status_code=200)

    # Step 1: Retrieve or initialize user tracking document
    user_tracking_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

    # Extract main fields
    user_events = user_data.get('events', [])
    current_event_id = user_data.get('current_event_id')
    awaiting_event_id = user_data.get('awaiting_event_id', False)
    awaiting_event_change_confirmation = user_data.get('awaiting_event_change_confirmation', False)
    last_inactivity_prompt = user_data.get('last_inactivity_prompt', None)
    awaiting_extra_questions = user_data.get('awaiting_extra_questions', False)
    current_extra_question_index = user_data.get('current_extra_question_index', 0)
    invalid_attempts = user_data.get('invalid_attempts', 0)

    # Remove duplicates in user_events
    user_events = UserTrackingService.deduplicate_events(user_events)
    UserTrackingService.update_user_events(normalized_phone, user_events)

    # Validate current event
    if current_event_id:
        if not EventService.event_exists(current_event_id):
            user_events = [e for e in user_events if e['event_id'] != current_event_id]
            UserTrackingService.update_user(normalized_phone, {
                'current_event_id': None,
                'events': user_events,
                'awaiting_event_id': True
            })
            send_message(From, f"The event '{current_event_id}' is no longer active. Please enter a new event ID to continue.")
            return Response(status_code=200)

    # Step 2: Handle inactivity (24h check)
    current_time = datetime.utcnow()
    user_inactive = False
    if user_events:
        last_times = [
            datetime.fromisoformat(e['timestamp'])
            for e in user_events if e.get('timestamp')
        ]
        if last_times and (current_time - max(last_times) > timedelta(hours=24)):
            user_inactive = True

    if user_inactive:
        if last_inactivity_prompt:
            prompt_time = datetime.fromisoformat(last_inactivity_prompt)
            if current_time - prompt_time >= timedelta(hours=24):
                event_list = '\n'.join(f"{i+1}. {e['event_id']}" for i,e in enumerate(user_events))
                send_message(From,
                    f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
                UserTrackingService.update_user(normalized_phone, {'last_inactivity_prompt': current_time.isoformat()})
                return Response(status_code=200)
        else:
            event_list = '\n'.join(f"{i+1}. {e['event_id']}" for i,e in enumerate(user_events))
            send_message(From,
                f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
            UserTrackingService.update_user(normalized_phone, {'last_inactivity_prompt': current_time.isoformat()})
            return Response(status_code=200)

    # Step 3: If user was prompted to pick an event after inactivity
    if last_inactivity_prompt and current_event_id:
        if Body.isdigit() and 1 <= int(Body) <= len(user_events):
            selected = user_events[int(Body)-1]['event_id']
            send_message(From, f"You are now continuing in event {selected}.")
            current_event_id = selected
            user_events = UserTrackingService.add_or_update_event(user_events, selected, datetime.utcnow())
            UserTrackingService.update_user(normalized_phone, {
                'current_event_id': current_event_id,
                'events': user_events,
                'last_inactivity_prompt': None,
                'invalid_attempts': 0
            })
            return Response(status_code=200)
        else:
            invalid_attempts += 1
            if invalid_attempts < 2:
                UserTrackingService.update_user(normalized_phone, {'invalid_attempts': invalid_attempts})
                send_message(From, "Invalid selection. Please reply with the number of the event you'd like to continue.")
                return Response(status_code=200)
            else:
                if current_event_id:
                    send_message(From, f"No valid selection made. Continuing with your current event '{current_event_id}'.")
                    user_events = UserTrackingService.add_or_update_event(user_events, current_event_id, datetime.utcnow())
                    UserTrackingService.update_user(normalized_phone, {
                        'current_event_id': current_event_id,
                        'events': user_events,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)
                else:
                    send_message(From, "No valid selection and no current event. Please provide your event ID.")
                    UserTrackingService.update_user(normalized_phone, {
                        'awaiting_event_id': True,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)

    # Step 4: Handle event change confirmation
    if awaiting_event_change_confirmation:
        if Body.strip().lower() in ['yes','y']:
            new_eid = user_data.get('new_event_id_pending')
            if not event_id_valid(new_eid):
                send_message(From, f"The event ID '{new_eid}' is invalid. Please enter a new event ID.")
                user_tracking_ref.update({
                    'awaiting_event_change_confirmation': False,
                    'new_event_id_pending': None,
                    'awaiting_event_id': True
                })
                return Response(status_code=200)
            current_event_id = new_eid
            user_events = UserTrackingService.add_or_update_event(user_events, current_event_id, datetime.utcnow())
            UserTrackingService.update_user(normalized_phone, {
                'current_event_id': current_event_id,
                'events': user_events,
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })
            init_msg = EventService.get_initial_message(current_event_id)
            extra, enabled = EventService.get_ordered_extra_questions(current_event_id)
            if enabled:
                UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions':True,'current_extra_question_index':0})
                first = enabled[0]
                send_message(From, f"{init_msg}\n\n{extra[first]['text']}")
            else:
                send_message(From, f"You have switched to event {current_event_id}.")
            return Response(status_code=200)
        else:
            UserTrackingService.update_user(normalized_phone, {
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None
            })
            send_message(From, f"Event change canceled. You remain in event {current_event_id}.")
            return Response(status_code=200)

    # Step 5: Handle when awaiting a new event ID
    if awaiting_event_id:
        extracted = extract_event_id_with_llm(Body)
        if extracted and event_id_valid(extracted):
            current_event_id = extracted
            user_events = UserTrackingService.add_or_update_event(user_events, current_event_id, datetime.utcnow())
            UserTrackingService.update_user(normalized_phone, {
                'events':user_events,
                'current_event_id':current_event_id,
                'awaiting_event_id':False,
                'awaiting_extra_questions':False,
                'current_extra_question_index':0
            })
            init_msg = EventService.get_initial_message(current_event_id)
            extra, enabled = EventService.get_ordered_extra_questions(current_event_id)
            if enabled:
                UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions':True,'current_extra_question_index':0})
                first = enabled[0]
                send_message(From, f"{init_msg}\n\n{extra[first]['text']}")
            else:
                name = ParticipantService.get_participant_name(current_event_id, normalized_phone)
                send_message(From, create_welcome_message(current_event_id, name))
            return Response(status_code=200)
        else:
            send_message(From, "Invalid event ID. Please re-enter or contact support.")
            return Response(status_code=200)

    # Step 6: Extra-questions flow
    if awaiting_extra_questions and current_event_id:
        if MediaUrl0:
            resp = requests.get(MediaUrl0, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
            ctype = resp.headers.get('Content-Type','')
            if 'audio' in ctype:
                audio_stream = io.BytesIO(resp.content)
                audio_stream.name = 'file.ogg'
                try:
                    tr = client.audio.transcriptions.create(model="whisper-1", file=audio_stream)
                    Body = tr.text
                except Exception as e:
                    return Response(status_code=500, content=str(e))
            else:
                return Response(status_code=400, content="Unsupported media type.")
        if not EventService.event_exists(current_event_id):
            UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions':False})
            send_message(From, "No event info found. Continue with survey.")
            return Response(status_code=200)
        extra, enabled = EventService.get_ordered_extra_questions(current_event_id)
        if current_extra_question_index < len(enabled):
            key = enabled[current_extra_question_index]
            qinfo = extra[key]
            fid = qinfo.get('id')
            if fid == "extract_name_with_llm":
                val = extract_name_with_llm(Body, current_event_id)
                ParticipantService.update_participant(current_event_id, normalized_phone, {key: val, 'name': val})
            elif fid == "extract_age_with_llm":
                ParticipantService.update_participant(current_event_id, normalized_phone, {key: extract_age_with_llm(Body, current_event_id)})
            elif fid == "extract_gender_with_llm":
                ParticipantService.update_participant(current_event_id, normalized_phone, {key: extract_gender_with_llm(Body, current_event_id)})
            elif fid == "extract_region_with_llm":
                ParticipantService.update_participant(current_event_id, normalized_phone, {key: extract_region_with_llm(Body, current_event_id)})
            else:
                ParticipantService.update_participant(current_event_id, normalized_phone, {key: Body})
            current_extra_question_index += 1
            UserTrackingService.update_user(normalized_phone, {'current_extra_question_index': current_extra_question_index})
            if current_extra_question_index < len(enabled):
                nxt = enabled[current_extra_question_index]
                send_message(From, extra[nxt]['text'])
            else:
                UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions':False})
                name = ParticipantService.get_participant_name(current_event_id, normalized_phone)
                send_message(From, create_welcome_message(current_event_id, name))
        return Response(status_code=200)

    # Step 7: If user has no current event ID
    if not current_event_id:
        extracted = extract_event_id_with_llm(Body)
        if extracted and event_id_valid(extracted):
            current_event_id = extracted
            user_events = UserTrackingService.add_or_update_event(user_events, current_event_id, datetime.utcnow())
            UserTrackingService.update_user(normalized_phone, {
                'events':user_events,
                'current_event_id':current_event_id,
                'awaiting_event_id':False,
                'awaiting_extra_questions':False,
                'current_extra_question_index':0
            })
            ParticipantService.update_participant(current_event_id, normalized_phone, {'event_id':current_event_id})
            init_msg = EventService.get_initial_message(current_event_id)
            extra, enabled = EventService.get_ordered_extra_questions(current_event_id)
            if enabled:
                UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions':True,'current_extra_question_index':0})
                first = enabled[0]
                send_message(From, f"{init_msg}\n\n{extra[first]['text']}")
            else:
                send_message(From, init_msg)
            return Response(status_code=200)
        else:
            send_message(From, "Welcome! Please provide your event ID to proceed.")
            UserTrackingService.update_user(normalized_phone, {'awaiting_event_id':True})
            return Response(status_code=200)

    # Step 8: Handle "change name" or "change event"
    if Body.lower().startswith("change name "):
        new_name = Body[12:].strip()
        if new_name:
            ParticipantService.update_participant(current_event_id, normalized_phone, {'name':new_name})
            send_message(From, f"Your name has been updated to {new_name}. Please continue.")
        else:
            send_message(From, "Error updating name. Please try again.")
        return Response(status_code=200)
    if Body.lower().startswith("change event "):
        new_eid = Body[13:].strip()
        if event_id_valid(new_eid):
            if new_eid == current_event_id:
                send_message(From, f"You are already in event {new_eid}.")
                return Response(status_code=200)
            send_message(From, f"You requested to change to event {new_eid}. Confirm 'yes' or 'no'.")
            UserTrackingService.update_user(normalized_phone, {
                'awaiting_event_change_confirmation':True,
                'new_event_id_pending':new_eid
            })
        else:
            send_message(From, f"The event ID '{new_eid}' is invalid.")
        return Response(status_code=200)

    # Step 9: Handle survey finalization
    if Body.strip().lower() in ['finalize','finish']:
        send_message(From, "Survey ended. Thank you for participating!")
        ParticipantService.update_participant(current_event_id, normalized_phone, {'survey_complete':True})
        return Response(status_code=200)
    
    # --- Interaction limit enforcement ---
    interaction_limit = get_interaction_limit(current_event_id)
    interaction_count = ParticipantService.get_interaction_count(current_event_id, normalized_phone)

    if interaction_count >= interaction_limit:
        logger.info(f"[Survey] {normalized_phone} exceeded interaction limit ({interaction_count} >= {interaction_limit}) for {current_event_id}")
        db.collection("users_exceeding_limit").document(normalized_phone).set({
            "phone": normalized_phone,
            "event_id": current_event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_interactions": interaction_count,
            "limit_used": interaction_limit
        }, merge=True)

        send_message(From, f"You have reached your interaction limit ({interaction_limit}) for this survey. Please contact AOI for assistance.")
        return Response(status_code=200)


    # Step 10: Survey question loop
    progress = ParticipantService.get_survey_progress(current_event_id, normalized_phone)
    questions_asked = progress['questions_asked']
    responses = progress['responses']
    last_qid = progress['last_question_id']

    if last_qid is not None:
        # Handle audio transcription for voice responses
        if MediaUrl0:
            resp = requests.get(MediaUrl0, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
            ctype = resp.headers.get('Content-Type','')
            if 'audio' in ctype:
                audio_stream = io.BytesIO(resp.content)
                audio_stream.name = 'file.ogg'
                try:
                    tr = client.audio.transcriptions.create(model="whisper-1", file=audio_stream)
                    Body = tr.text
                except Exception as e:
                    return Response(status_code=500, content=str(e))
            else:
                return Response(status_code=400, content="Unsupported media type.")

        responses[str(last_qid)] = Body
        interaction = {'message': Body}
        ParticipantService.update_participant(current_event_id, normalized_phone, {
            'responses': responses,
            'last_question_id': None
        })
        ParticipantService.append_interaction(current_event_id, normalized_phone, interaction)

    questions = EventService.get_survey_questions(current_event_id)

    updated = False
    for q in questions:
        qid = str(q["id"])
        if qid not in questions_asked:
            questions_asked[qid] = False
            updated = True
    if updated:
        ParticipantService.update_participant(current_event_id, normalized_phone, {'questions_asked': questions_asked})

    next_q = None
    for q in questions:
        if not questions_asked.get(str(q["id"]), False):
            next_q = q
            break

    if next_q:
        qtext = next_q["text"]
        send_message(From, qtext)
        questions_asked[str(next_q["id"])] = True
        interaction = {'response': qtext}
        ParticipantService.update_participant(current_event_id, normalized_phone, {
            'questions_asked': questions_asked,
            'last_question_id': next_q["id"]
        })
        ParticipantService.append_interaction(current_event_id, normalized_phone, interaction)
    else:
        completion_msg = EventService.get_completion_message(current_event_id)
        send_message(From, completion_msg)
        ParticipantService.update_participant(current_event_id, normalized_phone, {'survey_complete': True})

    return Response(status_code=200)
