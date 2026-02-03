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
from app.deliberation.second_round_agent import run_second_round_for_user
from app.utils.blocklist_helpers import get_interaction_limit, is_blocked_number  
import random

from config.config import (
    db, logger, client, twilio_client,
    twilio_number, assistant_id,
    twilio_account_sid, twilio_auth_token
)
from app.utils.validators import is_valid_name
from app.utils.listener_helpers import generate_bot_instructions
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

from app.utils.validators import _norm, normalize_event_path, normalize_phone
from app.services.firestore_service import (
    UserTrackingService,
    EventService,
    ParticipantService
)

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4.1-mini")


async def reply_listener(Body: str, From: str, MediaUrl0: str = None):
    logger.info(f"Received message from {From} with body '{Body}' and media URL {MediaUrl0}")

    normalized_phone = normalize_phone(From)

    if is_blocked_number(normalized_phone):
        logger.warning(f"[Blacklist] Ignoring message from blocked number: {normalized_phone}")
        return Response(status_code=200)

    # Step 1: Retrieve or initialize user tracking document
    _, user_data = UserTrackingService.get_or_create_user(normalized_phone)

    # Extract main fields from user_data
    user_events = user_data.get('events', [])
    current_event_id = user_data.get('current_event_id')
    awaiting_event_id = user_data.get('awaiting_event_id', False)
    awaiting_event_change_confirmation = user_data.get('awaiting_event_change_confirmation', False)
    last_inactivity_prompt = user_data.get('last_inactivity_prompt', None)
    # Extra question logic
    awaiting_extra_questions = user_data.get('awaiting_extra_questions', False)
    current_extra_question_index = user_data.get('current_extra_question_index', 0)
    invalid_attempts = user_data.get('invalid_attempts', 0)

    # Remove duplicates in user_events (keep the latest)
    user_events = UserTrackingService.deduplicate_events(user_events)
    UserTrackingService.update_user_events(normalized_phone, user_events)

    # Validate current event
    if current_event_id:
        if not EventService.event_exists(current_event_id):
            # The event no longer exists
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
        last_interaction_times = []
        for evt in user_events:
            event_timestamp = evt.get('timestamp', None)
            if event_timestamp:
                event_time = datetime.fromisoformat(event_timestamp)
                last_interaction_times.append(event_time)

        if last_interaction_times:
            most_recent_interaction = max(last_interaction_times)
            time_since_last_interaction = current_time - most_recent_interaction
            if time_since_last_interaction > timedelta(hours=24):
                user_inactive = True

    # Inactivity prompt logic
    if user_inactive:
        if last_inactivity_prompt:
            last_prompt_time = datetime.fromisoformat(last_inactivity_prompt)
            time_since_last_prompt = current_time - last_prompt_time
            # Only prompt once every 24 hours
            if time_since_last_prompt < timedelta(hours=24):
                pass
            else:
                event_list = '\n'.join([f"{i+1}. {evt['event_id']}" for i, evt in enumerate(user_events)])
                send_message(From, f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
                UserTrackingService.update_user(normalized_phone, {'last_inactivity_prompt': current_time.isoformat()})
                return Response(status_code=200)
        else:
            event_list = '\n'.join([f"{i+1}. {evt['event_id']}" for i, evt in enumerate(user_events)])
            send_message(From, f"You have been inactive for more than 24 hours.\nYour events:\n{event_list}\nPlease reply with the number of the event you'd like to continue.")
            UserTrackingService.update_user(normalized_phone, {'last_inactivity_prompt': current_time.isoformat()})
            return Response(status_code=200)

    # Step 3: If user was prompted to pick an event after inactivity
    if last_inactivity_prompt:
        if Body.isdigit() and 1 <= int(Body) <= len(user_events):
            selected_event = user_events[int(Body) - 1]['event_id']
            send_message(From, f"You are now continuing in event {selected_event}.")
            current_event_id = selected_event

            current_time_iso = datetime.utcnow().isoformat()
            for evt in user_events:
                if evt['event_id'] == selected_event:
                    evt['timestamp'] = current_time_iso
                    break

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
                send_message(From, "Invalid event selection. Please reply with the number corresponding to the event you'd like to continue.")
                return Response(status_code=200)
            else:
                if current_event_id:
                    send_message(From, f"No valid selection made. Continuing with your current event '{current_event_id}'.")
                    current_time_iso = datetime.utcnow().isoformat()
                    for evt in user_events:
                        if evt['event_id'] == current_event_id:
                            evt['timestamp'] = current_time_iso
                            break
                    UserTrackingService.update_user(normalized_phone, {
                        'current_event_id': current_event_id,
                        'events': user_events,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)
                else:
                    send_message(From, "No valid selection made and no current event found. Please provide your event ID to proceed.")
                    UserTrackingService.update_user(normalized_phone, {
                        'awaiting_event_id': True,
                        'last_inactivity_prompt': None,
                        'invalid_attempts': 0
                    })
                    return Response(status_code=200)

    # Step 4: If user was in the process of confirming event change
    if awaiting_event_change_confirmation:
        if Body.strip().lower() in ['yes', 'y']:
            new_event_id = user_data.get('new_event_id_pending')
            if not event_id_valid(new_event_id):
                send_message(From, f"The event ID '{new_event_id}' is no longer valid. Please enter a new event ID.")
                UserTrackingService.update_user(normalized_phone, {
                    'awaiting_event_change_confirmation': False,
                    'new_event_id_pending': None,
                    'awaiting_event_id': True
                })
                return Response(status_code=200)

            # Switch to new event
            current_event_id = new_event_id
            current_time_iso = datetime.utcnow().isoformat()

            event_exists = False
            for evt in user_events:
                if evt['event_id'] == current_event_id:
                    evt['timestamp'] = current_time_iso
                    event_exists = True
                    break
            if not event_exists:
                user_events.append({
                    'event_id': current_event_id,
                    'timestamp': current_time_iso
                })

            UserTrackingService.update_user(normalized_phone, {
                'current_event_id': current_event_id,
                'events': user_events,
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })

            # Initialize participant doc if necessary
            ParticipantService.initialize_participant(current_event_id, normalized_phone)

            # Send the new event's initial message (if exists)
            initial_message = EventService.get_initial_message(current_event_id)

            send_message(From, f"You have switched to event {current_event_id}.")
            #send_message(From, initial_message)

            # Start the extra-questions flow if any are enabled
            extra_questions, enabled_questions = EventService.get_ordered_extra_questions(current_event_id)

            if enabled_questions:
                    UserTrackingService.update_user(normalized_phone, {
                        'awaiting_extra_questions': True,
                        'current_extra_question_index': 0
                    })
                    first_question_key = enabled_questions[0]
                    first_question_text = extra_questions[first_question_key]['text']
                    #send_message(From, first_question_text)


                    combined_msg = f"{initial_message}\n\n{first_question_text}"
                    send_message(From, combined_msg)


            return Response(status_code=200)
        else:
            UserTrackingService.update_user(normalized_phone, {
                'awaiting_event_change_confirmation': False,
                'new_event_id_pending': None
            })
            send_message(From, f"Event change cancelled. You remain in event {current_event_id}. Please continue.")
            return Response(status_code=200)

    # Step 5: If we are awaiting a brand new event ID
    if awaiting_event_id:
        extracted_event_id = extract_event_id_with_llm(Body)
        if extracted_event_id and event_id_valid(extracted_event_id):
            # Valid event
            event_id = extracted_event_id
            current_event_id = event_id
            current_time_iso = datetime.utcnow().isoformat()

            # Mark or update user event list
            event_exists = False
            for evt in user_events:
                if evt['event_id'] == event_id:
                    evt['timestamp'] = current_time_iso
                    event_exists = True
                    break
            if not event_exists:
                user_events.append({
                    'event_id': event_id,
                    'timestamp': current_time_iso
                })

            UserTrackingService.update_user(normalized_phone, {
                'events': user_events,
                'current_event_id': current_event_id,
                'awaiting_event_id': False,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })


            ParticipantService.initialize_participant(event_id, normalized_phone)

            initial_message = EventService.get_initial_message(current_event_id)

            #send_message(From, initial_message) #instead to ensure the order i ll send the combined message-

            # Check if there are enabled extra questions
            extra_questions, enabled_questions = EventService.get_ordered_extra_questions(current_event_id)

            if enabled_questions:
                    UserTrackingService.update_user(normalized_phone, {
                        'awaiting_extra_questions': True,
                        'current_extra_question_index': 0
                    })
                    first_question_key = enabled_questions[0]
                    first_question_text = extra_questions[first_question_key]['text']
                    #send_message(From, first_question_text)

                    combined_msg = f"{initial_message}\n\n{first_question_text}"
                    send_message(From, combined_msg)

            else:
                participant_name = ParticipantService.get_participant_name(current_event_id, normalized_phone)
                welcome_msg = create_welcome_message(current_event_id, participant_name=participant_name)
                send_message(From, welcome_msg)

            return Response(status_code=200)
        else:
            logger.info(f"Invalid event ID: {Body}")
            send_message(From, "The event ID you provided is invalid. Please re-enter the correct event ID or contact support.")
            return Response(status_code=200)

    # Step 6: Handle extra questions if we are in that mode
    if awaiting_extra_questions and current_event_id:
        # Possibly handle audio -> transcribe
        if MediaUrl0:
            response = requests.get(MediaUrl0, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
            content_type = response.headers['Content-Type']
            if 'audio' in content_type:
                audio_stream = io.BytesIO(response.content)
                audio_stream.name = 'file.ogg'
                try:
                    transcription_result = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_stream
                    )
                    Body = transcription_result.text
                except Exception as e:
                    return Response(status_code=500, content=str(e))
            else:
                return Response(status_code=400, content="Unsupported media type.")

        # Load the event details and the question
        extra_questions, enabled_questions = EventService.get_ordered_extra_questions(current_event_id)

        if not enabled_questions:
            UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions': False})
            send_message(From, "No event info found. You can proceed with normal conversation.")
            return Response(status_code=200)

        # Get participant doc
        participant_data = ParticipantService.get_participant(current_event_id, normalized_phone) or {}

        # If we still have a question to ask
        if current_extra_question_index < len(enabled_questions):
            question_key = enabled_questions[current_extra_question_index]
            question_info = extra_questions[question_key]
            function_id = question_info.get('id', None)

            if function_id == "extract_name_with_llm":
                name_val = extract_name_with_llm(Body, current_event_id)
                # Store the extracted name in both the question_key field and "name"
                ParticipantService.update_participant(current_event_id, normalized_phone, {question_key: name_val, "name": name_val})

            elif function_id == "extract_age_with_llm":
                age_val = extract_age_with_llm(Body, current_event_id)
                ParticipantService.update_participant(current_event_id, normalized_phone, {question_key: age_val})

            elif function_id == "extract_gender_with_llm":
                gender_val = extract_gender_with_llm(Body, current_event_id)
                ParticipantService.update_participant(current_event_id, normalized_phone, {question_key: gender_val})

            elif function_id == "extract_region_with_llm":
                region_val = extract_region_with_llm(Body, current_event_id)
                ParticipantService.update_participant(current_event_id, normalized_phone, {question_key: region_val})

            else:
                # No recognized function, just store raw response
                ParticipantService.update_participant(current_event_id, normalized_phone, {question_key: Body})

            # Move to next question
            current_extra_question_index += 1
            UserTrackingService.update_user(normalized_phone, {'current_extra_question_index': current_extra_question_index})

            # If more questions remain, ask the next one
            if current_extra_question_index < len(enabled_questions):
                next_question_key = enabled_questions[current_extra_question_index]
                next_question_text = extra_questions[next_question_key]['text']
                send_message(From, next_question_text)
            else:
                # Done with extra questions
                UserTrackingService.update_user(normalized_phone, {'awaiting_extra_questions': False})
                # Fetch updated name
                participant_name = ParticipantService.get_participant_name(current_event_id, normalized_phone)

                # Send welcome message with the name (if valid)
                welcome_msg = create_welcome_message(current_event_id, participant_name=participant_name)
                send_message(From, welcome_msg)

        return Response(status_code=200)

    # Step 7: If user has no current event ID
    if not current_event_id:
        # Attempt to extract an event ID from the body
        extracted_event_id = extract_event_id_with_llm(Body)
        if extracted_event_id and event_id_valid(extracted_event_id):
            event_id = extracted_event_id
            current_event_id = event_id
            current_time_iso = datetime.utcnow().isoformat()

            event_exists = False
            for evt in user_events:
                if evt['event_id'] == event_id:
                    evt['timestamp'] = current_time_iso
                    event_exists = True
                    break
            if not event_exists:
                user_events.append({
                    'event_id': event_id,
                    'timestamp': current_time_iso
                })

            UserTrackingService.update_user(normalized_phone, {
                'events': user_events,
                'current_event_id': current_event_id,
                'awaiting_event_id': False,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0
            })

            ParticipantService.initialize_participant(event_id, normalized_phone)

            initial_message = EventService.get_initial_message(current_event_id)
            send_message(From, initial_message)

            # Check for extra questions
            extra_questions, enabled_questions = EventService.get_ordered_extra_questions(current_event_id)

            if enabled_questions:
                    UserTrackingService.update_user(normalized_phone, {
                        'awaiting_extra_questions': True,
                        'current_extra_question_index': 0
                    })
                    first_key = enabled_questions[0]
                    first_text = extra_questions[first_key]['text']
                    send_message(From, first_text)
            else:
                participant_name = ParticipantService.get_participant_name(current_event_id, normalized_phone)
                welcome_msg = create_welcome_message(current_event_id, participant_name=participant_name)
                send_message(From, welcome_msg)

            return Response(status_code=200)
        else:
            send_message(From, "Welcome! Please provide your event ID to proceed.")
            UserTrackingService.update_user(normalized_phone, {'awaiting_event_id': True})
            return Response(status_code=200)

    # Step 8: Handle "change name" or "change event" commands
    if Body.lower().startswith("change name "):
        new_name = Body[12:].strip()
        if new_name:
            ParticipantService.set_participant_name(current_event_id, normalized_phone, new_name)
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
            UserTrackingService.update_user(normalized_phone, {
                'awaiting_event_change_confirmation': True,
                'new_event_id_pending': new_event_id
            })
        else:
            send_message(From, f"The event ID '{new_event_id}' is invalid. Please check and try again.")
        return Response(status_code=200)

    # Step 9: Handle user finishing or finalizing
    if Body.strip().lower() in ['finalize', 'finish']:
        completion_message = EventService.get_completion_message(current_event_id)
        send_message(From, completion_message)
        return Response(status_code=200)

    # Step 10: Otherwise, normal conversation with the LLM
    welcome_message = EventService.get_welcome_message(current_event_id)
    if not welcome_message:
        welcome_message = "Welcome! You can now start sending text and audio messages."

    event_instructions = generate_bot_instructions(current_event_id)

    # If there's media, try to transcribe if audio
    if MediaUrl0:
        response = requests.get(MediaUrl0, auth=HTTPBasicAuth(twilio_account_sid, twilio_auth_token))
        content_type = response.headers['Content-Type']
        if 'audio' in content_type:
            audio_stream = io.BytesIO(response.content)
            audio_stream.name = 'file.ogg'
            try:
                transcription_result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_stream
                )
                Body = transcription_result.text
            except Exception as e:
                return Response(status_code=500, content=str(e))
        else:
            return Response(status_code=400, content="Unsupported media type.")

    if not Body:
        return Response(status_code=400)

# ----------------------------
# 2ND-ROUND DELIBERATION PATH
# ----------------------------
    if current_event_id and EventService.is_second_round_enabled(current_event_id):
        sr_reply = run_second_round_for_user(current_event_id, normalized_phone, user_msg=Body)

        # Use transactional method to prevent duplicate processing
        success = ParticipantService.process_second_round_interaction(
            current_event_id,
            normalized_phone,
            Body,
            sr_reply,
            normalize_func=_norm
        )

        if not success:
            return Response(status_code=200)

        if sr_reply:
            send_message(From, sr_reply)
        else:
            logger.warning("[2nd-round] Missing context or GPT error—falling back to normal flow.")

        return Response(status_code=200)
    # ---- end 2nd-round branch; normal flow continues below ----

    # Store user message
    ParticipantService.initialize_participant(current_event_id, normalized_phone)

    # Check interaction limit using the new configurable limit
    interaction_count = ParticipantService.get_interaction_count(current_event_id, normalized_phone)
    interaction_limit = get_interaction_limit(current_event_id)

    if interaction_count >= interaction_limit:
        logger.info(f"[Listener Mode] {normalized_phone} reached interaction limit "
                f"({interaction_count} / {interaction_limit}) for {current_event_id}")
        # Log event for moderation
        db.collection("users_exceeding_limit").document(normalized_phone).set({
            "phone": normalized_phone,
            "event_id": current_event_id,
            "timestamp": datetime.utcnow().isoformat(),
            "total_interactions": interaction_count,
            "limit_used": interaction_limit
        }, merge=True)

        send_message(From, f"You have reached your interaction limit ({interaction_limit}) for this event. Please contact AOI for assistance.")
        return Response(status_code=200)

    # Send user prompt to LLM
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=Body
    )

    ParticipantService.append_interaction(current_event_id, normalized_phone, {'message': Body})

    try:
        # Attempt to fetch model configuration from Firestore
        event_info = EventService.get_event_info(current_event_id)

        # Pre-initialize with the environment or constant default
        default_model = DEFAULT_MODEL
        if event_info:
            default_model = event_info.get("default_model", default_model)

        logger.info(f"[LLM Config] Using model from Firestore: {default_model}")

    except Exception as e:
        logger.error(f"[LLM Config] Failed to fetch model from Firestore, defaulting to {DEFAULT_MODEL}: {e}")
        default_model = DEFAULT_MODEL


    try:
        # Primary model attempt
        logger.info(f"[LLM Run] Starting primary run with model: {default_model}")

        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant_id,
            instructions=event_instructions,
            model=default_model
        )

        logger.info(f"[LLM Debug] Primary run status: {getattr(run, 'status', 'N/A')}")

        # Fallback if the primary model failed or didn’t complete
        if run.status != "completed":
            logger.warning(f"[LLM Fallback] Model {default_model} failed, retrying with {FALLBACK_MODEL}")

            if hasattr(run, 'last_error'):
                logger.error(f"[LLM Debug] last_error (primary): {run.last_error}")
            if hasattr(run, 'incomplete_details'):
                logger.error(f"[LLM Debug] incomplete_details (primary): {run.incomplete_details}")

            run = client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=assistant_id,
                instructions=event_instructions,
                model=FALLBACK_MODEL
            )

            logger.info(f"[LLM Debug] Fallback run status: {getattr(run, 'status', 'N/A')}")

    except Exception as e:
        logger.exception(f"[LLM Exception] Error while creating run: {e}")
        run = None


    # --- RESPONSE HANDLING ---
    if run and run.status == "completed":
        final_model = getattr(run, 'model', default_model)
        logger.info(f"[LLM Success] Final model used: {final_model}")

        messages = client.beta.threads.messages.list(thread_id=thread.id)
        assistant_response = extract_text_from_messages(messages)

        send_message(From, assistant_response)
        ParticipantService.append_interaction(current_event_id, normalized_phone, {
            'response': assistant_response,
            'model': final_model,
            'fallback': False
        })
    else:
        logger.warning("[LLM Fallback] Both models failed or returned incomplete response.")

        if run and hasattr(run, 'last_error'):
            logger.error(f"[LLM Debug] last_error (final): {run.last_error}")
        if run and hasattr(run, 'incomplete_details'):
            logger.error(f"[LLM Debug] incomplete_details (final): {run.incomplete_details}")

        fallback_responses = [
            "Agreed.",
            "Please continue.",
            "That’s an interesting point, tell me more.",
            "I understand.",
            "Go on, I’m listening."
        ]
        fallback_message = random.choice(fallback_responses)

        send_message(From, fallback_message)
        ParticipantService.append_interaction(current_event_id, normalized_phone, {
            'response': fallback_message,
            'model': None,
            'fallback': True
        })

    return Response(status_code=200)