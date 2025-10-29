
import logging
import json
import os
import io
import re
from uuid import uuid4
from datetime import datetime, timedelta

from firebase_admin import credentials, firestore

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
from app.utils.survey_helpers import initialize_user_document
from app.utils.validators import normalize_event_path
from app.utils.blacklist_helpers import get_interaction_limit,is_blocked_number  


async def reply_survey(Body: str, From: str, MediaUrl0: str = None):
    logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

    # Normalize phone number
    normalized_phone = From.replace("+", "").replace("-", "").replace(" ", "")
        # Check if number is blacklisted
    if is_blocked_number(normalized_phone):
        logger.warning(f"[Blacklist] Ignoring message from blocked number: {normalized_phone}")
        return Response(status_code=200)

    # Step 1: Retrieve or initialize user tracking document
    user_tracking_ref = db.collection('user_event_tracking').document(normalized_phone)
    user_tracking_doc = user_tracking_ref.get()
    if user_tracking_doc.exists:
        user_data = user_tracking_doc.to_dict()
    else:
        user_data = {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        user_tracking_ref.set(user_data)

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

    # Validate current event
    if current_event_id:
        event_info_ref = db.collection(normalize_event_path(current_event_id)).document('info')
        event_info_doc = event_info_ref.get()
        if not event_info_doc.exists:
            user_events = [e for e in user_events if e['event_id'] != current_event_id]
            user_tracking_ref.update({
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
                user_tracking_ref.update({'last_inactivity_prompt': current_time.isoformat()})
                return Response(status_code=200)
        else:
            event_list = '\n'.join(f"{i+1}. {e['event_id']}" for i,e in enumerate(user_events))
            send_message(From,
                f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
            user_tracking_ref.update({'last_inactivity_prompt': current_time.isoformat()})
            return Response(status_code=200)

    # Step 3: If user was prompted to pick an event after inactivity
    if last_inactivity_prompt and current_event_id:
        if Body.isdigit() and 1 <= int(Body) <= len(user_events):
            selected = user_events[int(Body)-1]['event_id']
            send_message(From, f"You are now continuing in event {selected}.")
            current_event_id = selected
            now_iso = datetime.utcnow().isoformat()
            for e in user_events:
                if e['event_id'] == selected:
                    e['timestamp'] = now_iso
                    break
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
                send_message(From, "Invalid selection. Please reply with the number of the event you'd like to continue.")
                return Response(status_code=200)
            else:
                if current_event_id:
                    send_message(From, f"No valid selection made. Continuing with your current event '{current_event_id}'.")
                    now_iso = datetime.utcnow().isoformat()
                    for e in user_events:
                        if e['event_id'] == current_event_id:
                            e['timestamp'] = now_iso
                            break
                    user_tracking_ref.update({
                        'current_event_id': current_event_id,
                        'events': user_events,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)
                else:
                    send_message(From, "No valid selection and no current event. Please provide your event ID.")
                    user_tracking_ref.update({
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
            now_iso = datetime.utcnow().isoformat()
            found = False
            for e in user_events:
                if e['event_id'] == current_event_id:
                    e['timestamp'] = now_iso
                    found = True
                    break
            if not found:
                user_events.append({'event_id': current_event_id, 'timestamp': now_iso})
            user_tracking_ref.update({
                'current_event_id': current_event_id,
                'events': user_events,
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })
            info_doc = db.collection(normalize_event_path(current_event_id)).document('info').get()
            init_msg = "Thank you for agreeing to participate..."
            if info_doc.exists:
                init_msg = info_doc.to_dict().get('initial_message', init_msg)
            extra = info_doc.to_dict().get('extra_questions', {}) if info_doc.exists else {}
            items = [(k,v) for k,v in extra.items() if v.get('enabled')]
            items.sort(key=lambda x:x[1].get('order',9999))
            enabled = [i[0] for i in items]
            if enabled:
                user_tracking_ref.update({'awaiting_extra_questions':True,'current_extra_question_index':0})
                first = enabled[0]
                send_message(From, f"{init_msg}\n\n{extra[first]['text']}")
            else:
                send_message(From, f"You have switched to event {current_event_id}.")
            return Response(status_code=200)
        else:
            user_tracking_ref.update({
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
            now_iso = datetime.utcnow().isoformat()
            found = False
            for e in user_events:
                if e['event_id'] == current_event_id:
                    e['timestamp'] = now_iso
                    found = True
                    break
            if not found:
                user_events.append({'event_id':current_event_id,'timestamp':now_iso})
            user_tracking_ref.update({
                'events':user_events,
                'current_event_id':current_event_id,
                'awaiting_event_id':False,
                'awaiting_extra_questions':False,
                'current_extra_question_index':0
            })
            info_doc = db.collection(normalize_event_path(current_event_id)).document('info').get()
            init_msg = "Thank you for agreeing to participate..."
            if info_doc.exists:
                init_msg = info_doc.to_dict().get('initial_message', init_msg)
            extra = info_doc.to_dict().get('extra_questions', {}) if info_doc.exists else {}
            items = [(k,v) for k,v in extra.items() if v.get('enabled')]
            items.sort(key=lambda x:x[1].get('order',9999))
            enabled = [i[0] for i in items]
            if enabled:
                user_tracking_ref.update({'awaiting_extra_questions':True,'current_extra_question_index':0})
                first = enabled[0]
                send_message(From, f"{init_msg}\n\n{extra[first]['text']}")
            else:
                part = db.collection(normalize_event_path(current_event_id)).document(normalized_phone).get()
                name = part.to_dict().get('name') if part.exists else None
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
        info_doc = db.collection(normalize_event_path(current_event_id)).document('info').get()
        if not info_doc.exists:
            user_tracking_ref.update({'awaiting_extra_questions':False})
            send_message(From, "No event info found. Continue with survey.")
            return Response(status_code=200)
        extra = info_doc.to_dict().get('extra_questions', {})
        items = [(k,v) for k,v in extra.items() if v.get('enabled')]
        items.sort(key=lambda x:x[1].get('order',9999))
        enabled = [i[0] for i in items]
        ev_doc_ref = db.collection(normalize_event_path(current_event_id)).document(normalized_phone)
        if current_extra_question_index < len(enabled):
            key = enabled[current_extra_question_index]
            qinfo = extra[key]
            fid = qinfo.get('id')
            if fid == "extract_name_with_llm":
                val = extract_name_with_llm(Body, current_event_id)
                ev_doc_ref.update({key: val, 'name': val})
            elif fid == "extract_age_with_llm":
                ev_doc_ref.update({key: extract_age_with_llm(Body, current_event_id)})
            elif fid == "extract_gender_with_llm":
                ev_doc_ref.update({key: extract_gender_with_llm(Body, current_event_id)})
            elif fid == "extract_region_with_llm":
                ev_doc_ref.update({key: extract_region_with_llm(Body, current_event_id)})
            else:
                ev_doc_ref.update({key: Body})
            current_extra_question_index += 1
            user_tracking_ref.update({'current_extra_question_index': current_extra_question_index})
            if current_extra_question_index < len(enabled):
                nxt = enabled[current_extra_question_index]
                send_message(From, extra[nxt]['text'])
            else:
                user_tracking_ref.update({'awaiting_extra_questions':False})
                part = db.collection(normalize_event_path(current_event_id)).document(normalized_phone).get().to_dict()
                send_message(From, create_welcome_message(current_event_id, part.get('name')))
        return Response(status_code=200)

    # Step 7: If user has no current event ID
    if not current_event_id:
        extracted = extract_event_id_with_llm(Body)
        if extracted and event_id_valid(extracted):
            current_event_id = extracted
            now_iso = datetime.utcnow().isoformat()
            found = False
            for e in user_events:
                if e['event_id'] == current_event_id:
                    e['timestamp'] = now_iso
                    found = True
                    break
            if not found:
                user_events.append({'event_id':current_event_id,'timestamp':now_iso})
            user_tracking_ref.update({
                'events':user_events,
                'current_event_id':current_event_id,
                'awaiting_event_id':False,
                'awaiting_extra_questions':False,
                'current_extra_question_index':0
            })
            ev_ref = db.collection(normalize_event_path(current_event_id)).document(normalized_phone)
            ev_ref.set({'event_id':current_event_id}, merge=True)
            info_doc = db.collection(normalize_event_path(current_event_id)).document('info').get()
            init_msg = "Thank you for agreeing to participate..."
            if info_doc.exists:
                init_msg = info_doc.to_dict().get('initial_message', init_msg)
            extra = info_doc.to_dict().get('extra_questions', {}) if info_doc.exists else {}
            items = [(k,v) for k,v in extra.items() if v.get('enabled')]
            items.sort(key=lambda x:x[1].get('order',9999))
            enabled = [i[0] for i in items]
            if enabled:
                user_tracking_ref.update({'awaiting_extra_questions':True,'current_extra_question_index':0})
                first = enabled[0]
                send_message(From, f"{init_msg}\n\n{extra[first]['text']}")
            else:
                send_message(From, init_msg)
            return Response(status_code=200)
        else:
            send_message(From, "Welcome! Please provide your event ID to proceed.")
            user_tracking_ref.update({'awaiting_event_id':True})
            return Response(status_code=200)

    # Step 8: Handle "change name" or "change event"
    if Body.lower().startswith("change name "):
        new_name = Body[12:].strip()
        if new_name:
            db.collection(normalize_event_path(current_event_id)).document(normalized_phone).update({'name':new_name})
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
            user_tracking_ref.update({
                'awaiting_event_change_confirmation':True,
                'new_event_id_pending':new_eid
            })
        else:
            send_message(From, f"The event ID '{new_eid}' is invalid.")
        return Response(status_code=200)

    # Step 9: Handle survey finalization
    if Body.strip().lower() in ['finalize','finish']:
        send_message(From, "Survey ended. Thank you for participating!")
        db.collection(normalize_event_path(current_event_id)).document(normalized_phone).update({'survey_complete':True}    )
        return Response(status_code=200)
    
    # --- Interaction limit enforcement ---
    interaction_limit = get_interaction_limit(current_event_id)
    participant_ref = db.collection(normalize_event_path(current_event_id)).document(normalized_phone)
    participant_doc = participant_ref.get()
    participant_data = participant_doc.to_dict() if participant_doc.exists else {}
    interactions = participant_data.get('interactions', [])

    if len(interactions) >= interaction_limit:
        logger.info(f"[Survey] {normalized_phone} exceeded interaction limit ({len(interactions)} >= {interaction_limit}) for {current_event_id}")
        db.collection("users_exceeding_limit").document(normalized_phone).set({
            "phone": normalized_phone,
            "event_id": current_event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_interactions": len(interactions),
            "limit_used": interaction_limit
        }, merge=True)

        send_message(From, f"You have reached your interaction limit ({interaction_limit}) for this survey. Please contact AOI for assistance.")
        return Response(status_code=200)


    # Step 10: Survey question loop
    ev_ref = db.collection(normalize_event_path(current_event_id)).document(normalized_phone)
    ev_doc = ev_ref.get().to_dict()
    questions_asked = ev_doc.get('questions_asked', {})
    responses = ev_doc.get('responses', {})
    last_qid = ev_doc.get('last_question_id')

    if last_qid is not None:
        responses[str(last_qid)] = Body
        ev_ref.update({
            'responses': responses,
            'last_question_id': None,
            'interactions': firestore.ArrayUnion([{'message': Body}])
        })

    info_ref = db.collection(normalize_event_path(current_event_id)).document("info")
    info_doc = info_ref.get()
    questions = info_doc.to_dict().get("questions", []) if info_doc.exists else []

    updated = False
    for q in questions:
        qid = str(q["id"])
        if qid not in questions_asked:
            questions_asked[qid] = False
            updated = True
    if updated:
        ev_ref.update({'questions_asked': questions_asked})

    next_q = None
    for q in questions:
        if not questions_asked.get(str(q["id"]), False):
            next_q = q
            break

    if next_q:
        qtext = next_q["text"]
        send_message(From, qtext)
        questions_asked[str(next_q["id"])] = True
        ev_ref.update({
            'questions_asked': questions_asked,
            'last_question_id': next_q["id"],
            'interactions': firestore.ArrayUnion([{'response': qtext}])
        })
    else:
        send_message(From, info_doc.to_dict().get("completion_message", "You’ve completed the survey—thank you!"))
        ev_ref.update({'survey_complete': True})

    return Response(status_code=200)
