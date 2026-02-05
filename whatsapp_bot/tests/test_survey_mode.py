"""
Comprehensive unit tests for SurveyMode handler.

These tests cover all major flows in the survey mode including:
- User initialization and tracking
- Event validation and switching
- Inactivity handling
- Extra questions flow
- Survey question loop
- Error cases and edge conditions
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import io
import sys

from fastapi import Response

# Mock config module before importing handlers
sys.modules['config.config'] = MagicMock()

# Mock blocklist and normalization helpers
sys.modules['app.utils.blocklist_helpers'] = MagicMock()
sys.modules['app.utils.validators'] = MagicMock()

# Import the handler we're testing
from app.handlers.SurveyMode import reply_survey

# Patch the blocklist and normalization functions globally
patch('app.handlers.SurveyMode.is_blocked_number', return_value=False).start()
patch('app.handlers.SurveyMode.normalize_phone', side_effect=lambda x: x.replace("+", "").replace("-", "").replace(" ", "")).start()
patch('app.handlers.SurveyMode.get_interaction_limit', return_value=1000).start()


def get_recent_timestamp():
    """Helper to get a recent timestamp to avoid inactivity detection."""
    return datetime.utcnow().isoformat()


class TestSurveyModeUserInitialization(unittest.IsolatedAsyncioTestCase):
    """Test cases for user initialization and tracking."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_new_user_no_event_prompts_for_event_id(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that a new user with no event ID is prompted to provide one."""
        # Setup: New user with no events
        mock_doc_ref = MagicMock()
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
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = []

        # Execute
        result = await reply_survey(Body="Hello", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("provide your event id", call_args[1].lower())
        mock_user_svc.update_user.assert_called_with('1234567890', {'awaiting_event_id': True})

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_user_deduplication_called(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that event deduplication is called on user retrieval."""
        mock_doc_ref = MagicMock()
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event1', 'timestamp': '2024-01-01T11:00:00'}
        ]
        user_data = {
            'events': events,
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = [events[1]]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_survey_questions.return_value = []
        mock_event_svc.get_completion_message.return_value = "Done"

        # Execute
        await reply_survey(Body="Test", From="+1234567890")

        # Assert
        mock_user_svc.deduplicate_events.assert_called_once_with(events)
        mock_user_svc.update_user_events.assert_called_once()


class TestSurveyModeEventValidation(unittest.IsolatedAsyncioTestCase):
    """Test cases for event validation and switching."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_invalid_current_event_prompts_for_new(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that an invalid current event prompts user to provide new event ID."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'invalid_event', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'invalid_event',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = False

        # Execute
        result = await reply_survey(Body="Test", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("no longer active", call_args[1].lower())
        mock_user_svc.update_user.assert_called_with('1234567890', {
            'current_event_id': None,
            'events': [],
            'awaiting_event_id': True
        })

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.extract_event_id_with_llm')
    @patch('app.handlers.SurveyMode.event_id_valid')
    async def test_valid_event_id_extraction_creates_event(self, mock_valid, mock_extract, mock_send,
                                                           mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that a valid extracted event ID initializes the event."""
        mock_doc_ref = MagicMock()
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
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = []
        mock_user_svc.add_or_update_event.return_value = [{'event_id': 'event123', 'timestamp': '2024-01-01T10:00:00'}]

        mock_extract.return_value = 'event123'
        mock_valid.return_value = True
        mock_event_svc.get_initial_message.return_value = "Welcome to the survey!"
        mock_event_svc.get_ordered_extra_questions.return_value = ({}, [])

        # Execute
        result = await reply_survey(Body="My event is event123", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_extract.assert_called_once_with("My event is event123")
        mock_valid.assert_called_once_with('event123')
        mock_user_svc.add_or_update_event.assert_called_once()
        mock_user_svc.update_user.assert_called()
        mock_send.assert_called_once()


class TestSurveyModeInactivityHandling(unittest.IsolatedAsyncioTestCase):
    """Test cases for inactivity detection and handling."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_inactive_user_gets_prompted(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that an inactive user (>24h) gets prompted to select event."""
        mock_doc_ref = MagicMock()
        old_timestamp = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        user_data = {
            'events': [
                {'event_id': 'event1', 'timestamp': old_timestamp},
                {'event_id': 'event2', 'timestamp': old_timestamp}
            ],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute
        result = await reply_survey(Body="Test", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("inactive", call_args[1].lower())
        self.assertIn("event1", call_args[1])
        self.assertIn("event2", call_args[1])

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_valid_event_selection_after_inactivity(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that selecting a valid event number after inactivity works."""
        mock_doc_ref = MagicMock()
        old_timestamp = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        recent_prompt = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        user_data = {
            'events': [
                {'event_id': 'event1', 'timestamp': old_timestamp},
                {'event_id': 'event2', 'timestamp': old_timestamp}
            ],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': recent_prompt,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_user_svc.add_or_update_event.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute - user selects event 2
        result = await reply_survey(Body="2", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("event2", call_args[1].lower())
        mock_user_svc.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_invalid_event_selection_increments_attempts(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that invalid event selection increments invalid_attempts."""
        mock_doc_ref = MagicMock()
        recent_prompt = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': recent_prompt}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': recent_prompt,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute - user selects invalid number
        result = await reply_survey(Body="99", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("invalid", call_args[1].lower())
        mock_user_svc.update_user.assert_called_with('1234567890', {'invalid_attempts': 1})


class TestSurveyModeEventChangeConfirmation(unittest.IsolatedAsyncioTestCase):
    """Test cases for event change confirmation flow."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.event_id_valid')
    async def test_change_event_command_prompts_confirmation(self, mock_valid, mock_send, mock_event_svc, mock_user_svc):
        """Test that 'change event' command prompts for confirmation."""
        mock_doc_ref = MagicMock()
        # Use recent timestamp to avoid inactivity detection
        recent_timestamp = datetime.utcnow().isoformat()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': recent_timestamp}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True
        mock_valid.return_value = True

        # Execute
        result = await reply_survey(Body="change event event2", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("confirm", call_args[1].lower())
        self.assertIn("event2", call_args[1])
        mock_user_svc.update_user.assert_called_with('1234567890', {
            'awaiting_event_change_confirmation': True,
            'new_event_id_pending': 'event2'
        })

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.event_id_valid')
    async def test_event_change_confirmation_yes(self, mock_valid, mock_send, mock_event_svc, mock_user_svc):
        """Test that confirming 'yes' to event change switches event."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': True,
            'new_event_id_pending': 'event2',
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_user_svc.add_or_update_event.return_value = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_valid.return_value = True
        mock_event_svc.get_initial_message.return_value = "Welcome to event2"
        mock_event_svc.get_ordered_extra_questions.return_value = ({}, [])

        # Execute
        result = await reply_survey(Body="yes", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_user_svc.add_or_update_event.assert_called_once()
        mock_send.assert_called_once()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_event_change_confirmation_no(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that replying 'no' to event change cancels the change."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': True,
            'new_event_id_pending': 'event2',
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']

        # Execute
        result = await reply_survey(Body="no", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("cancel", call_args[1].lower())
        mock_user_svc.update_user.assert_called_with('1234567890', {
            'awaiting_event_change_confirmation': False,
            'new_event_id_pending': None
        })


class TestSurveyModeExtraQuestions(unittest.IsolatedAsyncioTestCase):
    """Test cases for extra questions flow."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.extract_name_with_llm')
    async def test_extra_question_name_extraction(self, mock_extract_name, mock_send,
                                                   mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that name extraction extra question works correctly."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': True,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_ordered_extra_questions.return_value = (
            {
                'name_question': {
                    'id': 'extract_name_with_llm',
                    'text': 'What is your name?',
                    'enabled': True,
                    'order': 1
                },
                'age_question': {
                    'id': 'extract_age_with_llm',
                    'text': 'What is your age?',
                    'enabled': True,
                    'order': 2
                }
            },
            ['name_question', 'age_question']
        )
        mock_extract_name.return_value = 'John Doe'

        # Execute
        result = await reply_survey(Body="My name is John Doe", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_extract_name.assert_called_once_with("My name is John Doe", 'event1')
        mock_part_svc.update_participant.assert_called_with(
            'event1', '1234567890', {'name_question': 'John Doe', 'name': 'John Doe'}
        )
        mock_user_svc.update_user.assert_called_with('1234567890', {'current_extra_question_index': 1})
        mock_send.assert_called_once()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.create_welcome_message')
    async def test_extra_questions_completion_sends_welcome(self, mock_welcome, mock_send,
                                                            mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that completing all extra questions sends welcome message."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': True,
            'current_extra_question_index': 0,  # Answering the last question
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_ordered_extra_questions.return_value = (
            {'q1': {'id': 'generic', 'text': 'Q1?', 'enabled': True, 'order': 1}},
            ['q1']  # Only 1 question
        )
        mock_part_svc.get_participant_name.return_value = 'John Doe'
        mock_welcome.return_value = "Welcome John Doe to the survey!"

        # Execute
        result = await reply_survey(Body="Answer to last question", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        # Should update index first, then mark as complete
        mock_user_svc.update_user.assert_any_call('1234567890', {'current_extra_question_index': 1})
        mock_user_svc.update_user.assert_any_call('1234567890', {'awaiting_extra_questions': False})
        mock_part_svc.get_participant_name.assert_called_once_with('event1', '1234567890')
        mock_welcome.assert_called_once_with('event1', 'John Doe')
        mock_send.assert_called_once()


class TestSurveyModeSurveyQuestions(unittest.IsolatedAsyncioTestCase):
    """Test cases for survey question loop."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_first_survey_question_sent(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that the first survey question is sent to user."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_survey_questions.return_value = [
            {'id': 1, 'text': 'What is your opinion on topic A?'},
            {'id': 2, 'text': 'What is your opinion on topic B?'}
        ]
        mock_part_svc.get_survey_progress.return_value = {
            'questions_asked': {},
            'responses': {},
            'last_question_id': None
        }
        mock_part_svc.get_interaction_count.return_value = 0

        # Execute
        result = await reply_survey(Body="Start survey", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("topic A", call_args[1])
        mock_part_svc.update_participant.assert_called()
        mock_part_svc.append_interaction.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_answer_recorded_next_question_sent(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that answer is recorded and next question is sent."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_survey_questions.return_value = [
            {'id': 1, 'text': 'What is your opinion on topic A?'},
            {'id': 2, 'text': 'What is your opinion on topic B?'}
        ]
        mock_part_svc.get_survey_progress.return_value = {
            'questions_asked': {'1': True},
            'responses': {},
            'last_question_id': 1  # User just answered question 1
        }
        mock_part_svc.get_interaction_count.return_value = 0

        # Execute
        result = await reply_survey(Body="I think topic A is important", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        # Should record answer
        update_calls = mock_part_svc.update_participant.call_args_list
        self.assertTrue(any('responses' in str(call) for call in update_calls))
        # Should send next question
        mock_send.assert_called()
        call_args = mock_send.call_args[0]
        self.assertIn("topic B", call_args[1])

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_survey_completion_sends_completion_message(self, mock_send, mock_part_svc,
                                                              mock_event_svc, mock_user_svc):
        """Test that completing all questions sends completion message."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_survey_questions.return_value = [
            {'id': 1, 'text': 'What is your opinion on topic A?'}
        ]
        mock_event_svc.get_completion_message.return_value = "Thank you for completing the survey!"
        mock_part_svc.get_survey_progress.return_value = {
            'questions_asked': {'1': True},  # All questions asked
            'responses': {'1': 'My answer'},
            'last_question_id': 1
        }
        mock_part_svc.get_interaction_count.return_value = 0

        # Execute
        result = await reply_survey(Body="My final answer", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_event_svc.get_completion_message.assert_called_once_with('event1')
        mock_send.assert_called()
        call_args = mock_send.call_args[0]
        self.assertIn("thank you", call_args[1].lower())
        # Should mark survey as complete
        update_calls = mock_part_svc.update_participant.call_args_list
        self.assertTrue(any('survey_complete' in str(call) for call in update_calls))


class TestSurveyModeFinalization(unittest.IsolatedAsyncioTestCase):
    """Test cases for survey finalization commands."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_finalize_command_ends_survey(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that 'finalize' command ends the survey."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute
        result = await reply_survey(Body="finalize", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("thank you", call_args[1].lower())
        mock_part_svc.update_participant.assert_called_with(
            'event1', '1234567890', {'survey_complete': True}
        )

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_finish_command_ends_survey(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that 'finish' command ends the survey."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute
        result = await reply_survey(Body="finish", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_part_svc.update_participant.assert_called_with(
            'event1', '1234567890', {'survey_complete': True}
        )


class TestSurveyModeNameChange(unittest.IsolatedAsyncioTestCase):
    """Test cases for name change functionality."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_change_name_updates_participant(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that 'change name' command updates participant name."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute
        result = await reply_survey(Body="change name Jane Smith", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_part_svc.update_participant.assert_called_with(
            'event1', '1234567890', {'name': 'Jane Smith'}
        )
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("jane smith", call_args[1].lower())

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_change_name_empty_shows_error(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that empty name change shows error."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [{'event_id': 'event1', 'timestamp': get_recent_timestamp()}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = user_data['events']
        mock_event_svc.event_exists.return_value = True

        # Execute
        result = await reply_survey(Body="change name ", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("error", call_args[1].lower())


class TestSurveyModeEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Test cases for edge conditions and error handling."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.extract_event_id_with_llm')
    @patch('app.handlers.SurveyMode.event_id_valid')
    async def test_invalid_event_id_shows_error(self, mock_valid, mock_extract, mock_send,
                                                mock_event_svc, mock_user_svc):
        """Test that invalid event ID extraction shows error."""
        mock_doc_ref = MagicMock()
        user_data = {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': True,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        }
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = []
        mock_extract.return_value = 'invalid_id'
        mock_valid.return_value = False

        # Execute
        result = await reply_survey(Body="My event is invalid_id", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        self.assertIn("invalid", call_args[1].lower())

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    async def test_phone_number_normalization(self, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that phone numbers are properly normalized."""
        mock_doc_ref = MagicMock()
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
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = []

        # Execute with various phone number formats
        await reply_survey(Body="Test", From="+1-234-567-8900")

        # Assert - should normalize to 12345678900
        mock_user_svc.get_or_create_user.assert_called_with('12345678900')

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    async def test_empty_events_list_handled(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that empty events list is handled gracefully."""
        mock_doc_ref = MagicMock()
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
        mock_user_svc.get_or_create_user.return_value = (mock_doc_ref, user_data)
        mock_user_svc.deduplicate_events.return_value = []

        # Execute
        result = await reply_survey(Body="Hello", From="+1234567890")

        # Assert
        self.assertEqual(result.status_code, 200)
        # Should prompt for event ID
        mock_send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
