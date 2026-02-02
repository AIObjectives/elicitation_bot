"""
Database abstraction layer for Firestore operations.

This module provides a clean interface for all database operations,
encapsulating Firestore-specific logic and providing type-safe methods
for user tracking, event management, and participant data.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from firebase_admin import firestore

from config.config import db, logger


class UserTrackingService:
    """Handles operations on the user_event_tracking collection."""

    COLLECTION_NAME = 'user_event_tracking'

    @staticmethod
    def get_or_create_user(normalized_phone: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Retrieve or create a user tracking document.

        Args:
            normalized_phone: Normalized phone number (no +, -, or spaces)

        Returns:
            Tuple of (document_reference, user_data_dict)
        """
        doc_ref = db.collection(UserTrackingService.COLLECTION_NAME).document(normalized_phone)
        doc = doc_ref.get()

        if doc.exists:
            return doc_ref, doc.to_dict()

        # Initialize new user with default structure
        data = {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        doc_ref.set(data)
        logger.info(f"Created new user tracking document for {normalized_phone}")
        return doc_ref, data

    @staticmethod
    def get_user(normalized_phone: str) -> Optional[Dict[str, Any]]:
        """
        Get user tracking data without creating if it doesn't exist.

        Args:
            normalized_phone: Normalized phone number

        Returns:
            User data dict or None if not found
        """
        doc = db.collection(UserTrackingService.COLLECTION_NAME).document(normalized_phone).get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    def update_user(normalized_phone: str, data: Dict[str, Any]) -> None:
        """
        Update user tracking fields.

        Args:
            normalized_phone: Normalized phone number
            data: Fields to update
        """
        db.collection(UserTrackingService.COLLECTION_NAME).document(normalized_phone).update(data)
        logger.debug(f"Updated user {normalized_phone} with fields: {list(data.keys())}")

    @staticmethod
    def update_user_events(normalized_phone: str, events: List[Dict[str, Any]]) -> None:
        """
        Update the events array for a user.

        Args:
            normalized_phone: Normalized phone number
            events: List of event dictionaries with event_id and timestamp
        """
        db.collection(UserTrackingService.COLLECTION_NAME).document(normalized_phone).update({
            'events': events
        })

    @staticmethod
    def deduplicate_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate events, keeping the most recent timestamp.

        Args:
            events: List of event dictionaries

        Returns:
            Deduplicated list of events
        """
        unique_events = {}
        for event in events:
            event_id = event.get('event_id')
            if not event_id:
                continue

            if event_id not in unique_events:
                unique_events[event_id] = event
            else:
                existing_time = datetime.fromisoformat(unique_events[event_id]['timestamp'])
                new_time = datetime.fromisoformat(event['timestamp'])
                if new_time > existing_time:
                    unique_events[event_id] = event

        return list(unique_events.values())

    @staticmethod
    def add_or_update_event(events: List[Dict[str, Any]], event_id: str,
                           timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Add a new event or update existing event timestamp.

        Args:
            events: Current events list
            event_id: Event ID to add/update
            timestamp: Timestamp to use (defaults to now)

        Returns:
            Updated events list
        """
        if timestamp is None:
            timestamp = datetime.now()

        timestamp_str = timestamp.isoformat()

        # Update existing or add new
        updated = False
        for event in events:
            if event.get('event_id') == event_id:
                event['timestamp'] = timestamp_str
                updated = True
                break

        if not updated:
            events.append({'event_id': event_id, 'timestamp': timestamp_str})

        return events


class EventService:
    """Handles operations on event collections (AOI_eventid)."""

    @staticmethod
    def get_collection_name(event_id: str) -> str:
        """
        Get the normalized collection name for an event.

        Args:
            event_id: Event ID

        Returns:
            Collection name (e.g., 'AOI_event123')
        """
        from app.utils.validators import normalize_event_path
        return normalize_event_path(event_id)

    @staticmethod
    def event_exists(event_id: str) -> bool:
        """
        Check if an event exists by checking for the info document.

        Args:
            event_id: Event ID to check

        Returns:
            True if event exists, False otherwise
        """
        collection_name = EventService.get_collection_name(event_id)
        doc_ref = db.collection(collection_name).document('info')
        doc = doc_ref.get()
        return doc.exists

    @staticmethod
    def get_event_info(event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get event information from the info document.

        Args:
            event_id: Event ID

        Returns:
            Event info dict or None if not found
        """
        collection_name = EventService.get_collection_name(event_id)
        doc = db.collection(collection_name).document('info').get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    def get_event_mode(event_id: str) -> Optional[str]:
        """
        Get the mode of an event (listener, followup, survey).

        Args:
            event_id: Event ID

        Returns:
            Mode string or None
        """
        info = EventService.get_event_info(event_id)
        return info.get('mode') if info else None

    @staticmethod
    def get_initial_message(event_id: str) -> str:
        """
        Get the initial message for an event.

        Args:
            event_id: Event ID

        Returns:
            Initial message string (with default fallback)
        """
        info = EventService.get_event_info(event_id)
        default_message = "Thank you for agreeing to participate..."
        return info.get('initial_message', default_message) if info else default_message

    @staticmethod
    def get_welcome_message(event_id: str) -> str:
        """
        Get the welcome message for an event.

        Args:
            event_id: Event ID

        Returns:
            Welcome message string
        """
        info = EventService.get_event_info(event_id)
        return info.get('welcome_message', '') if info else ''

    @staticmethod
    def get_completion_message(event_id: str) -> str:
        """
        Get the completion message for an event.

        Args:
            event_id: Event ID

        Returns:
            Completion message string (with default fallback)
        """
        info = EventService.get_event_info(event_id)
        default_message = "Thank you. You have completed this survey!"
        return info.get('completion_message', default_message) if info else default_message

    @staticmethod
    def has_extra_questions(event_id: str) -> bool:
        """
        Check if an event has enabled extra questions.

        Args:
            event_id: Event ID

        Returns:
            True if event has any enabled extra questions
        """
        info = EventService.get_event_info(event_id)
        if not info:
            return False

        extra = info.get('extra_questions', {})
        return any(q.get('enabled') for q in extra.values())

    @staticmethod
    def get_ordered_extra_questions(event_id: str) -> Tuple[Dict[str, Any], List[str]]:
        """
        Get extra questions ordered by their order field.

        Args:
            event_id: Event ID

        Returns:
            Tuple of (questions_dict, ordered_keys_list)
        """
        info = EventService.get_event_info(event_id)
        if not info:
            return {}, []

        extra = info.get('extra_questions', {})
        enabled = {k: v for k, v in extra.items() if v.get('enabled')}
        ordered = sorted(enabled.items(), key=lambda item: item[1].get('order', 9999))
        keys = [k for k, v in ordered]
        questions = {k: v for k, v in enabled.items()}

        return questions, keys

    @staticmethod
    def get_survey_questions(event_id: str) -> List[Dict[str, Any]]:
        """
        Get survey questions for an event.

        Args:
            event_id: Event ID

        Returns:
            List of question dictionaries
        """
        info = EventService.get_event_info(event_id)
        return info.get('questions', []) if info else []

    @staticmethod
    def is_second_round_enabled(event_id: str) -> bool:
        """
        Check if second round deliberation is enabled for an event.

        Args:
            event_id: Event ID

        Returns:
            True if second round is enabled
        """
        info = EventService.get_event_info(event_id)
        if not info:
            return False

        # Check new field
        src = info.get('second_round_claims_source') or {}
        if isinstance(src, dict):
            val = src.get('enabled')
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.strip().lower() in {'true', '1', 'yes', 'on'}

        # Backward compatibility with legacy field
        legacy = info.get('second_deliberation_enabled')
        if isinstance(legacy, bool):
            return legacy
        if isinstance(legacy, str):
            return legacy.strip().lower() in {'true', '1', 'yes', 'on'}

        return False

    @staticmethod
    def get_second_round_config(event_id: str) -> Dict[str, Any]:
        """
        Get second round claims source configuration.

        Args:
            event_id: Event ID

        Returns:
            Configuration dict with collection and document fields
        """
        info = EventService.get_event_info(event_id)
        if not info:
            return {}

        return info.get('second_round_claims_source', {}) or {}

    @staticmethod
    def get_second_round_prompts(event_id: str) -> Dict[str, str]:
        """
        Get custom second round system and user prompts.

        Args:
            event_id: Event ID

        Returns:
            Dict with 'system_prompt' and 'user_prompt' keys
        """
        info = EventService.get_event_info(event_id)
        if not info:
            return {}

        prompts = info.get('second_round_prompts', {}) or {}
        return {
            'system_prompt': prompts.get('system_prompt', ''),
            'user_prompt': prompts.get('user_prompt', '')
        }


class ParticipantService:
    """Handles operations on participant documents within event collections."""

    @staticmethod
    def get_participant(event_id: str, normalized_phone: str) -> Optional[Dict[str, Any]]:
        """
        Get participant data for an event.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number

        Returns:
            Participant data dict or None if not found
        """
        collection_name = EventService.get_collection_name(event_id)
        doc = db.collection(collection_name).document(normalized_phone).get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    def initialize_participant(event_id: str, normalized_phone: str) -> None:
        """
        Initialize a participant document if it doesn't exist.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number
        """
        collection_name = EventService.get_collection_name(event_id)
        doc_ref = db.collection(collection_name).document(normalized_phone)
        doc = doc_ref.get()

        if not doc.exists:
            data = {
                'name': None,
                'interactions': [],
                'event_id': event_id
            }
            doc_ref.set(data)
            logger.info(f"Initialized participant {normalized_phone} for event {event_id}")

    @staticmethod
    def update_participant(event_id: str, normalized_phone: str, data: Dict[str, Any]) -> None:
        """
        Update participant fields.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number
            data: Fields to update
        """
        collection_name = EventService.get_collection_name(event_id)
        db.collection(collection_name).document(normalized_phone).update(data)
        logger.debug(f"Updated participant {normalized_phone} in event {event_id}")

    @staticmethod
    def append_interaction(event_id: str, normalized_phone: str,
                          interaction: Dict[str, Any]) -> None:
        """
        Append an interaction to a participant's interactions array.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number
            interaction: Interaction dict with message, response, and ts fields
        """
        collection_name = EventService.get_collection_name(event_id)
        db.collection(collection_name).document(normalized_phone).update({
            'interactions': firestore.ArrayUnion([interaction])
        })

    @staticmethod
    def append_second_round_interaction(event_id: str, normalized_phone: str,
                                       interaction: Dict[str, Any]) -> None:
        """
        Append an interaction to second_round_interactions array.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number
            interaction: Interaction dict with message/response and ts fields
        """
        collection_name = EventService.get_collection_name(event_id)
        db.collection(collection_name).document(normalized_phone).update({
            'second_round_interactions': firestore.ArrayUnion([interaction])
        })

    @staticmethod
    def get_interaction_count(event_id: str, normalized_phone: str) -> int:
        """
        Get the number of interactions for a participant.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number

        Returns:
            Number of interactions
        """
        data = ParticipantService.get_participant(event_id, normalized_phone)
        if not data:
            return 0

        interactions = data.get('interactions', [])
        return len(interactions)

    @staticmethod
    def get_participant_name(event_id: str, normalized_phone: str) -> Optional[str]:
        """
        Get participant's name.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number

        Returns:
            Name string or None
        """
        data = ParticipantService.get_participant(event_id, normalized_phone)
        return data.get('name') if data else None

    @staticmethod
    def set_participant_name(event_id: str, normalized_phone: str, name: str) -> None:
        """
        Set participant's name.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number
            name: Name to set
        """
        ParticipantService.update_participant(event_id, normalized_phone, {'name': name})

    @staticmethod
    def is_survey_complete(event_id: str, normalized_phone: str) -> bool:
        """
        Check if a participant has completed the survey.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number

        Returns:
            True if survey is marked complete
        """
        data = ParticipantService.get_participant(event_id, normalized_phone)
        return data.get('survey_complete', False) if data else False

    @staticmethod
    def get_survey_progress(event_id: str, normalized_phone: str) -> Dict[str, Any]:
        """
        Get survey progress for a participant.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number

        Returns:
            Dict with questions_asked, responses, and last_question_id
        """
        data = ParticipantService.get_participant(event_id, normalized_phone)
        if not data:
            return {
                'questions_asked': {},
                'responses': {},
                'last_question_id': None
            }

        return {
            'questions_asked': data.get('questions_asked', {}),
            'responses': data.get('responses', {}),
            'last_question_id': data.get('last_question_id')
        }

    @staticmethod
    def get_second_round_data(event_id: str, normalized_phone: str) -> Dict[str, Any]:
        """
        Get second round deliberation data for a participant.

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number

        Returns:
            Dict with summary, claims, interactions, and intro status
        """
        data = ParticipantService.get_participant(event_id, normalized_phone)
        if not data:
            return {
                'summary': None,
                'agreeable_claims': [],
                'opposing_claims': [],
                'claim_selection_reason': None,
                'second_round_interactions': [],
                'second_round_intro_done': False
            }

        return {
            'summary': data.get('summary'),
            'agreeable_claims': data.get('agreeable_claims', []) or [],
            'opposing_claims': data.get('opposing_claims', []) or [],
            'claim_selection_reason': data.get('claim_selection_reason'),
            'second_round_interactions': data.get('second_round_interactions', []) or [],
            'second_round_intro_done': bool(data.get('second_round_intro_done', False))
        }

    @staticmethod
    def process_second_round_interaction(event_id: str, normalized_phone: str,
                                        user_msg: str, sr_reply: str = None,
                                        normalize_func=None) -> bool:
        """
        Process a second-round interaction transactionally to prevent duplicates.

        This method uses Firestore transactions to ensure that duplicate user messages
        are not processed twice. It compares the incoming message with the last user
        message and skips processing if they match (after normalization).

        Args:
            event_id: Event ID
            normalized_phone: Normalized phone number
            user_msg: User's message
            sr_reply: Second-round agent's reply (optional)
            normalize_func: Function to normalize messages for comparison (optional)

        Returns:
            True if interaction was added, False if duplicate detected
        """
        from datetime import datetime

        collection_name = EventService.get_collection_name(event_id)
        doc_ref = db.collection(collection_name).document(normalized_phone)

        @firestore.transactional
        def _process_transaction(transaction, ref, msg, reply, norm_fn):
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() if snap.exists else {"second_round_interactions": []}
            interactions = data.get("second_round_interactions", [])

            # Check for duplicate message
            last_user_msg = None
            for item in reversed(interactions):
                if "message" in item:
                    last_user_msg = item["message"]
                    break

            # Compare normalized messages if normalization function provided
            if last_user_msg and norm_fn:
                if norm_fn(last_user_msg) == norm_fn(msg):
                    logger.info("[2nd-round] Duplicate user message detected; skipping re-run.")
                    return False
            elif last_user_msg == msg:
                logger.info("[2nd-round] Duplicate user message detected; skipping re-run.")
                return False

            # Add new interactions
            now_iso = datetime.utcnow().isoformat()
            interactions.append({"message": msg, "ts": now_iso})
            if reply:
                interactions.append({"response": reply, "ts": now_iso})

            transaction.set(ref, {"second_round_interactions": interactions}, merge=True)
            return True

        transaction = db.transaction()
        return _process_transaction(transaction, doc_ref, user_msg, sr_reply, normalize_func)


class ReportService:
    """Handles operations on report collections for second round deliberation."""

    @staticmethod
    def get_report_metadata(event_id: str) -> Dict[str, Any]:
        """
        Fetch report metadata based on event's second_round_claims_source config.

        Args:
            event_id: Event ID

        Returns:
            Report metadata dict
        """
        config = EventService.get_second_round_config(event_id)
        col = config.get('collection')
        doc_id = config.get('document')

        if not col or not doc_id:
            return {}

        doc = db.collection(col).document(doc_id).get()
        if not doc.exists:
            return {}

        data = doc.to_dict() or {}
        return data.get('metadata', {})


# Convenience functions for backward compatibility
def get_or_create_user(normalized_phone: str) -> Tuple[Any, Dict[str, Any]]:
    """Backward compatible wrapper for UserTrackingService.get_or_create_user"""
    return UserTrackingService.get_or_create_user(normalized_phone)


def event_exists(event_id: str) -> bool:
    """Backward compatible wrapper for EventService.event_exists"""
    return EventService.event_exists(event_id)


def get_event_info(event_id: str) -> Optional[Dict[str, Any]]:
    """Backward compatible wrapper for EventService.get_event_info"""
    return EventService.get_event_info(event_id)
