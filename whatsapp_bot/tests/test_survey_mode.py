"""
Unit tests for SurveyMode.py handler.

Tests cover:
- User initialization and tracking
- Event validation and switching
- Inactivity handling
- Extra questions flow
- Survey question progression
- Edge cases and error handling
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock config before importing SurveyMode
with patch.dict(os.environ, {
    'OPENAI_API_KEY': 'test_key',
    'TWILIO_ACCOUNT_SID': 'test_sid',
    'TWILIO_AUTH_TOKEN': 'test_token',
    'TWILIO_NUMBER': '+1234567890',
    'ASSISTANT_ID': 'test_assistant',
    'FIREBASE_CREDENTIALS_JSON': '{"type": "service_account", "project_id": "test"}'
}):
    # Mock firebase_admin before config imports it
    sys.modules['firebase_admin'] = MagicMock()
    sys.modules['firebase_admin.credentials'] = MagicMock()
    sys.modules['firebase_admin.firestore'] = MagicMock()

    from fastapi import Response
    from firebase_admin import firestore

    from app.handlers.SurveyMode import reply_survey


class TestSurveyModeUserTracking(unittest.TestCase):
    """Test cases for user tracking and initialization."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_new_user_initialization(self, mock_send_message, mock_user_service):
        """Test that a new user is properly initialized."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [],
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = []

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="test", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_user_service.get_or_create_user.assert_called_once_with('1234567890')
        mock_user_service.deduplicate_events.assert_called_once()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_duplicate_events_are_deduplicated(self, mock_send_message, mock_event_service, mock_user_service):
        """Test that duplicate events in user's event list are removed."""
        # Setup
        mock_ref = MagicMock()
        events_with_duplicates = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()},
            {'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'},
        ]
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': events_with_duplicates,
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        deduplicated = [{'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'}]
        mock_user_service.deduplicate_events.return_value = deduplicated

        # Execute
        import asyncio
        asyncio.run(reply_survey(Body="test", From="+1234567890"))

        # Assert
        mock_user_service.deduplicate_events.assert_called_once_with(events_with_duplicates)
        mock_user_service.update_user_events.assert_called_once_with('1234567890', deduplicated)


class TestSurveyModeEventValidation(unittest.TestCase):
    """Test cases for event validation and switching."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_invalid_event_prompts_for_new_event(self, mock_send_message, mock_event_service, mock_user_service):
        """Test that invalid/deleted events prompt user for new event ID."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'deleted_event', 'timestamp': '2024-01-01T10:00:00'}],
                'current_event_id': 'deleted_event',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'deleted_event', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = False

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="test", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_event_service.event_exists.assert_called_once_with('deleted_event')
        mock_user_service.update_user.assert_called_once()
        update_call_args = mock_user_service.update_user.call_args[0]
        self.assertEqual(update_call_args[0], '1234567890')
        self.assertIsNone(update_call_args[1]['current_event_id'])
        self.assertTrue(update_call_args[1]['awaiting_event_id'])
        mock_send_message.assert_called_once()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.extract_event_id_with_llm')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.send_message')
    def test_awaiting_event_id_with_valid_id(self, mock_send_message, mock_valid, mock_extract,
                                              mock_event_service, mock_user_service):
        """Test handling of valid event ID when awaiting."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [],
                'current_event_id': None,
                'awaiting_event_id': True,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = []
        mock_extract.return_value = 'valid_event_123'
        mock_valid.return_value = True
        mock_event_service.get_initial_message.return_value = "Welcome to the survey!"
        mock_event_service.get_ordered_extra_questions.return_value = ({}, [])

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="valid_event_123", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_extract.assert_called_once_with("valid_event_123")
        mock_valid.assert_called_once_with('valid_event_123')
        mock_user_service.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.extract_event_id_with_llm')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.send_message')
    def test_awaiting_event_id_with_invalid_id(self, mock_send_message, mock_valid,
                                                mock_extract, mock_user_service):
        """Test handling of invalid event ID when awaiting."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [],
                'current_event_id': None,
                'awaiting_event_id': True,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = []
        mock_extract.return_value = 'invalid_event'
        mock_valid.return_value = False

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="invalid_event", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("Invalid event ID", mock_send_message.call_args[0][1])


class TestSurveyModeInactivityHandling(unittest.TestCase):
    """Test cases for user inactivity detection and handling."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_inactive_user_receives_prompt(self, mock_send_message, mock_user_service):
        """Test that inactive users receive a prompt to select an event."""
        # Setup - user inactive for 25 hours
        old_timestamp = (datetime.utcnow() - timedelta(hours=25)).isoformat()
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
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
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': old_timestamp},
            {'event_id': 'event2', 'timestamp': old_timestamp}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="test", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("inactive", mock_send_message.call_args[0][1].lower())
        mock_user_service.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_valid_event_selection_after_inactivity(self, mock_send_message, mock_user_service):
        """Test valid event selection after inactivity prompt."""
        # Setup
        mock_ref = MagicMock()
        prompt_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [
                    {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()},
                    {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'}
                ],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': prompt_time,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'}
        ]

        # Execute - user selects event 1
        import asyncio
        result = asyncio.run(reply_survey(Body="1", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("continuing", mock_send_message.call_args[0][1].lower())
        mock_user_service.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_invalid_event_selection_after_inactivity(self, mock_send_message, mock_user_service):
        """Test invalid event selection after inactivity prompt."""
        # Setup
        mock_ref = MagicMock()
        prompt_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': prompt_time,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]

        # Execute - user selects invalid index
        import asyncio
        result = asyncio.run(reply_survey(Body="99", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("invalid", mock_send_message.call_args[0][1].lower())


class TestSurveyModeEventChanging(unittest.TestCase):
    """Test cases for event change confirmation flow."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.send_message')
    def test_change_event_valid_prompts_confirmation(self, mock_send_message, mock_valid, mock_user_service):
        """Test that changing to a valid event prompts for confirmation."""
        # Setup - use recent timestamp to avoid inactivity check
        recent_timestamp = datetime.utcnow().isoformat()
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': recent_timestamp}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': recent_timestamp}
        ]
        mock_valid.return_value = True

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="change event event2", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("confirm", mock_send_message.call_args[0][1].lower())
        mock_user_service.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.send_message')
    def test_confirm_event_change_yes(self, mock_send_message, mock_valid,
                                      mock_event_service, mock_user_service):
        """Test confirming event change with 'yes'."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': True,
                'new_event_id_pending': 'event2',
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_valid.return_value = True
        mock_event_service.get_initial_message.return_value = "Welcome!"
        mock_event_service.get_ordered_extra_questions.return_value = ({}, [])

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="yes", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_user_service.update_user.assert_called()


class TestSurveyModeExtraQuestions(unittest.TestCase):
    """Test cases for extra questions flow."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_extra_questions_flow(self, mock_send_message, mock_participant_service,
                                   mock_event_service, mock_user_service):
        """Test processing extra questions."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': True,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.get_ordered_extra_questions.return_value = (
            {
                'name': {'id': 'plain_text', 'text': 'What is your name?', 'order': 1},
                'age': {'id': 'plain_text', 'text': 'What is your age?', 'order': 2}
            },
            ['name', 'age']
        )

        # Execute - first question answer
        import asyncio
        result = asyncio.run(reply_survey(Body="John Doe", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_participant_service.update_participant.assert_called()
        mock_user_service.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.extract_name_with_llm')
    @patch('app.handlers.SurveyMode.send_message')
    def test_extra_question_with_llm_extraction(self, mock_send_message, mock_extract_name,
                                                 mock_participant_service, mock_event_service,
                                                 mock_user_service):
        """Test extra question that uses LLM extraction."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': True,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.get_ordered_extra_questions.return_value = (
            {
                'name': {'id': 'extract_name_with_llm', 'text': 'What is your name?', 'order': 1}
            },
            ['name']
        )
        mock_extract_name.return_value = "John Doe"

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="My name is John Doe", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_extract_name.assert_called_once()
        mock_participant_service.update_participant.assert_called()


class TestSurveyModeSurveyQuestions(unittest.TestCase):
    """Test cases for survey question loop."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.firestore')
    def test_survey_question_loop_first_question(self, mock_firestore, mock_send_message,
                                                   mock_participant_service, mock_event_service,
                                                   mock_user_service):
        """Test asking the first survey question."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_participant_service.get_survey_progress.return_value = {
            'questions_asked': {},
            'responses': {},
            'last_question_id': None
        }
        mock_event_service.get_survey_questions.return_value = [
            {'id': 1, 'text': 'What do you think about X?'},
            {'id': 2, 'text': 'How do you feel about Y?'}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="test", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("What do you think about X?", mock_send_message.call_args[0][1])

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.firestore')
    def test_survey_question_loop_answer_recorded(self, mock_firestore, mock_send_message,
                                                    mock_participant_service, mock_event_service,
                                                    mock_user_service):
        """Test that survey answers are recorded."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_participant_service.get_survey_progress.return_value = {
            'questions_asked': {'1': True},
            'responses': {},
            'last_question_id': 1
        }
        mock_event_service.get_survey_questions.return_value = [
            {'id': 1, 'text': 'What do you think about X?'},
            {'id': 2, 'text': 'How do you feel about Y?'}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="I think it's great!", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        # Verify answer was recorded
        update_calls = [call for call in mock_participant_service.update_participant.call_args_list]
        self.assertTrue(len(update_calls) > 0)

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    @patch('app.handlers.SurveyMode.firestore')
    def test_survey_completion(self, mock_firestore, mock_send_message, mock_participant_service,
                                mock_event_service, mock_user_service):
        """Test survey completion when all questions answered."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_participant_service.get_survey_progress.return_value = {
            'questions_asked': {'1': True, '2': True},
            'responses': {'1': 'answer1'},
            'last_question_id': 2
        }
        mock_event_service.get_survey_questions.return_value = [
            {'id': 1, 'text': 'Question 1'},
            {'id': 2, 'text': 'Question 2'}
        ]
        mock_event_service.get_completion_message.return_value = "Thank you for completing the survey!"

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="final answer", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_event_service.get_completion_message.assert_called_once()
        # Verify completion message sent
        self.assertIn("Thank you", mock_send_message.call_args[0][1])


class TestSurveyModeCommandHandling(unittest.TestCase):
    """Test cases for special commands."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_change_name_command(self, mock_send_message, mock_participant_service, mock_user_service):
        """Test changing participant name."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="change name John Smith", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_participant_service.set_participant_name.assert_called_once_with(
            'event1', '1234567890', 'John Smith'
        )
        mock_send_message.assert_called_once()
        self.assertIn("updated", mock_send_message.call_args[0][1].lower())

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_finalize_command(self, mock_send_message, mock_participant_service, mock_user_service):
        """Test survey finalization command."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="finalize", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_participant_service.update_participant.assert_called_once()
        update_call = mock_participant_service.update_participant.call_args
        self.assertTrue(update_call[0][2]['survey_complete'])


class TestSurveyModeAdditionalCoverage(unittest.TestCase):
    """Additional test cases for edge cases and less common paths."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_invalid_selection_max_attempts_no_current_event(self, mock_send_message, mock_user_service):
        """Test invalid selection after max attempts when no current event."""
        # Setup
        mock_ref = MagicMock()
        prompt_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': None,  # No current event
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': prompt_time,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 2  # Max attempts reached
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]

        # Execute - user gives invalid selection
        import asyncio
        result = asyncio.run(reply_survey(Body="invalid", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("event id", mock_send_message.call_args[0][1].lower())

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.extract_event_id_with_llm')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.create_welcome_message')
    @patch('app.handlers.SurveyMode.send_message')
    def test_no_current_event_with_new_event_and_participant(self, mock_send_message, mock_create_welcome,
                                                              mock_participant_service, mock_valid, mock_extract,
                                                              mock_event_service, mock_user_service):
        """Test user with no current event providing new event ID with existing participant."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [],
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = []
        mock_extract.return_value = 'new_event'
        mock_valid.return_value = True
        mock_event_service.get_initial_message.return_value = "Welcome!"
        mock_event_service.get_ordered_extra_questions.return_value = ({}, [])
        mock_participant_service.get_participant.return_value = {'name': 'John', 'event_id': 'new_event'}
        mock_create_welcome.return_value = "Welcome John!"

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="new_event", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_participant_service.get_participant.assert_called_once()
        mock_participant_service.update_participant.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.send_message')
    def test_event_change_confirmation_invalid_event(self, mock_send_message, mock_valid,
                                                      mock_event_service, mock_user_service):
        """Test event change confirmation with invalid event ID."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': True,
                'new_event_id_pending': 'invalid_event',
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_valid.return_value = False

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="yes", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("invalid", mock_send_message.call_args[0][1].lower())

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_event_change_confirmation_no(self, mock_send_message, mock_user_service):
        """Test declining event change."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': True,
                'new_event_id_pending': 'event2',
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="no", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_send_message.assert_called_once()
        self.assertIn("canceled", mock_send_message.call_args[0][1].lower())

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_extra_questions_last_question_completion(self, mock_send_message, mock_participant_service,
                                                       mock_event_service, mock_user_service):
        """Test completion of last extra question."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': True,
                'current_extra_question_index': 1,  # Last question
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.get_ordered_extra_questions.return_value = (
            {
                'name': {'id': 'plain_text', 'text': 'Name?', 'order': 1},
                'age': {'id': 'plain_text', 'text': 'Age?', 'order': 2}
            },
            ['name', 'age']
        )
        mock_participant_service.get_participant.return_value = {'name': 'John'}

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="25", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_user_service.update_user.assert_called()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.extract_age_with_llm')
    @patch('app.handlers.SurveyMode.extract_gender_with_llm')
    @patch('app.handlers.SurveyMode.extract_region_with_llm')
    @patch('app.handlers.SurveyMode.send_message')
    def test_extra_questions_with_different_llm_extractors(self, mock_send_message, mock_extract_region,
                                                            mock_extract_gender, mock_extract_age,
                                                            mock_participant_service, mock_event_service,
                                                            mock_user_service):
        """Test extra questions with different LLM extractors (age, gender, region)."""
        # Setup for age extraction
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': True,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.get_ordered_extra_questions.return_value = (
            {
                'age': {'id': 'extract_age_with_llm', 'text': 'Age?', 'order': 1},
                'gender': {'id': 'extract_gender_with_llm', 'text': 'Gender?', 'order': 2},
                'region': {'id': 'extract_region_with_llm', 'text': 'Region?', 'order': 3}
            },
            ['age', 'gender', 'region']
        )
        mock_extract_age.return_value = "25"
        mock_extract_gender.return_value = "Male"
        mock_extract_region.return_value = "North America"

        # Test age extraction
        import asyncio
        result = asyncio.run(reply_survey(Body="I am 25 years old", From="+1234567890"))
        self.assertEqual(result.status_code, 200)
        mock_extract_age.assert_called_once()

        # Test gender extraction
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': True,
                'current_extra_question_index': 1,
                'invalid_attempts': 0
            }
        )
        result = asyncio.run(reply_survey(Body="Male", From="+1234567890"))
        self.assertEqual(result.status_code, 200)
        mock_extract_gender.assert_called_once()

        # Test region extraction
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': True,
                'current_extra_question_index': 2,
                'invalid_attempts': 0
            }
        )
        result = asyncio.run(reply_survey(Body="North America", From="+1234567890"))
        self.assertEqual(result.status_code, 200)
        mock_extract_region.assert_called_once()

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.EventService')
    @patch('app.handlers.SurveyMode.extract_event_id_with_llm')
    @patch('app.handlers.SurveyMode.event_id_valid')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_no_current_event_with_extra_questions(self, mock_send_message, mock_participant_service,
                                                    mock_valid, mock_extract, mock_event_service,
                                                    mock_user_service):
        """Test no current event flow with extra questions enabled."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [],
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = []
        mock_extract.return_value = 'event123'
        mock_valid.return_value = True
        mock_event_service.get_initial_message.return_value = "Welcome!"
        mock_event_service.get_ordered_extra_questions.return_value = (
            {'name': {'id': 'plain_text', 'text': 'Name?', 'order': 1}},
            ['name']
        )
        mock_participant_service.get_participant.return_value = None

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="event123", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_participant_service.initialize_participant.assert_called_once()
        mock_send_message.assert_called_once()
        self.assertIn("welcome", mock_send_message.call_args[0][1].lower())


class TestSurveyModeEdgeCases(unittest.TestCase):
    """Test cases for edge cases and error handling."""

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_phone_number_normalization(self, mock_send_message, mock_user_service):
        """Test that phone numbers are properly normalized."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [],
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = []

        # Execute with formatted phone number
        import asyncio
        asyncio.run(reply_survey(Body="test", From="+1-234-567-8900"))

        # Assert - phone should be normalized to digits only
        mock_user_service.get_or_create_user.assert_called_once_with('12345678900')

    @patch('app.handlers.SurveyMode.UserTrackingService')
    @patch('app.handlers.SurveyMode.ParticipantService')
    @patch('app.handlers.SurveyMode.send_message')
    def test_empty_name_change_returns_error(self, mock_send_message, mock_participant_service,
                                              mock_user_service):
        """Test that empty name change returns error message."""
        # Setup
        mock_ref = MagicMock()
        mock_user_service.get_or_create_user.return_value = (
            mock_ref,
            {
                'events': [{'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}],
                'current_event_id': 'event1',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': datetime.utcnow().isoformat()}
        ]

        # Execute
        import asyncio
        result = asyncio.run(reply_survey(Body="change name ", From="+1234567890"))

        # Assert
        self.assertEqual(result.status_code, 200)
        mock_participant_service.set_participant_name.assert_not_called()
        mock_send_message.assert_called_once()
        self.assertIn("error", mock_send_message.call_args[0][1].lower())


if __name__ == '__main__':
    unittest.main()
