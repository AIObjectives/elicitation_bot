"""
Unit tests for ListenerMode handler.

These tests verify the behavior of the reply_listener function,
covering various user interaction scenarios, event handling, and
edge cases.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
import pytest

# Mock dependencies before importing the module
sys.modules['pydub'] = MagicMock()
sys.modules['firebase_admin'] = MagicMock()
sys.modules['decouple'] = MagicMock()
sys.modules['twilio'] = MagicMock()
sys.modules['twilio.rest'] = MagicMock()
sys.modules['openai'] = MagicMock()

# Import the function to test
from fastapi import Response
with patch.dict('sys.modules', {
    'app.deliberation.second_round_agent': MagicMock(),
    'config.config': MagicMock()
}):
    from app.handlers.ListenerMode import reply_listener


class TestListenerModeUserTracking(unittest.IsolatedAsyncioTestCase):
    """Test cases for user tracking operations."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_new_user_initialization(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that a new user is properly initialized."""
        # Setup
        normalized_phone = '1234567890'
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = []

        # Execute
        await reply_listener(Body='test123', From='+1234567890')

        # Assert
        mock_user_svc.get_or_create_user.assert_called_once_with(normalized_phone)
        mock_user_svc.deduplicate_events.assert_called_once()
        mock_user_svc.update_user_events.assert_called_once()

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_duplicate_events_removed(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that duplicate events are properly deduplicated."""
        # Setup
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'},
        ]
        deduplicated = [{'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'}]

        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': user_events,
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = deduplicated

        # Execute
        await reply_listener(Body='test', From='+1234567890')

        # Assert
        mock_user_svc.deduplicate_events.assert_called_once_with(user_events)
        mock_user_svc.update_user_events.assert_called_once_with('1234567890', deduplicated)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_invalid_event_cleared(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that invalid current event is cleared."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'invalid_event', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'invalid_event',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'invalid_event', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = False

        # Execute
        response = await reply_listener(Body='test', From='+1234567890')

        # Assert
        mock_event_svc.event_exists.assert_called_once_with('invalid_event')
        mock_user_svc.update_user.assert_called_once()
        update_call = mock_user_svc.update_user.call_args[0]
        self.assertIsNone(update_call[1]['current_event_id'])
        self.assertTrue(update_call[1]['awaiting_event_id'])
        mock_send.assert_called_once()
        self.assertEqual(response.status_code, 200)


class TestListenerModeInactivity(unittest.IsolatedAsyncioTestCase):
    """Test cases for inactivity handling."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.datetime')
    async def test_inactivity_prompt_after_24_hours(self, mock_dt, mock_send, mock_event_svc, mock_user_svc):
        """Test that inactivity prompt is sent after 24 hours."""
        # Setup
        now = datetime(2024, 1, 2, 12, 0, 0)
        old_timestamp = datetime(2024, 1, 1, 11, 0, 0).isoformat()

        mock_dt.utcnow.return_value = now
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'event1', 'timestamp': old_timestamp}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'event1', 'timestamp': old_timestamp}]
        mock_event_svc.event_exists.return_value = True

        # Execute
        response = await reply_listener(Body='test', From='+1234567890')

        # Assert
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('inactive', message.lower())
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_event_selection_after_inactivity(self, mock_send, mock_event_svc, mock_user_svc):
        """Test selecting an event after inactivity prompt."""
        # Setup
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'}
        ]

        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': user_events,
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': '2024-01-01T12:00:00',
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = user_events

        # Execute - selecting event 1
        response = await reply_listener(Body='1', From='+1234567890')

        # Assert
        mock_user_svc.update_user.assert_called()
        update_data = mock_user_svc.update_user.call_args[0][1]
        self.assertEqual(update_data['current_event_id'], 'event1')
        self.assertIsNone(update_data['last_inactivity_prompt'])
        self.assertEqual(update_data['invalid_attempts'], 0)
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_invalid_event_selection_retry(self, mock_send, mock_event_svc, mock_user_svc):
        """Test invalid event selection allows retry."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': '2024-01-01T12:00:00',
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}]

        # Execute - invalid selection
        response = await reply_listener(Body='99', From='+1234567890')

        # Assert
        mock_user_svc.update_user.assert_called_once()
        update_data = mock_user_svc.update_user.call_args[0][1]
        self.assertEqual(update_data['invalid_attempts'], 1)
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('Invalid', message)
        self.assertEqual(response.status_code, 200)


class TestListenerModeEventID(unittest.IsolatedAsyncioTestCase):
    """Test cases for event ID handling."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.extract_event_id_with_llm')
    @patch('app.handlers.ListenerMode.event_id_valid')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_valid_event_id_accepted(self, mock_send, mock_valid, mock_extract,
                                          mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that a valid event ID is accepted and processed."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': True,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = []
        mock_extract.return_value = 'test123'
        mock_valid.return_value = True
        mock_event_svc.get_initial_message.return_value = 'Welcome to test123!'
        mock_event_svc.get_ordered_extra_questions.return_value = ({}, [])
        mock_part_svc.get_participant_name.return_value = None

        with patch('app.handlers.ListenerMode.create_welcome_message') as mock_welcome:
            mock_welcome.return_value = 'Welcome!'

            # Execute
            response = await reply_listener(Body='test123', From='+1234567890')

            # Assert
            mock_extract.assert_called_once_with('test123')
            mock_valid.assert_called_once_with('test123')
            mock_part_svc.initialize_participant.assert_called_once_with('test123', '1234567890')
            mock_user_svc.update_user.assert_called()
            self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.extract_event_id_with_llm')
    @patch('app.handlers.ListenerMode.event_id_valid')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_invalid_event_id_rejected(self, mock_send, mock_valid, mock_extract,
                                            mock_event_svc, mock_user_svc):
        """Test that an invalid event ID is rejected."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': True,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = []
        mock_extract.return_value = 'invalid'
        mock_valid.return_value = False

        # Execute
        response = await reply_listener(Body='invalid', From='+1234567890')

        # Assert
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('invalid', message.lower())
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_no_event_id_prompts_user(self, mock_send, mock_event_svc, mock_user_svc):
        """Test that user is prompted for event ID when none exists."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = []

        with patch('app.handlers.ListenerMode.extract_event_id_with_llm') as mock_extract:
            with patch('app.handlers.ListenerMode.event_id_valid') as mock_valid:
                mock_extract.return_value = None
                mock_valid.return_value = False

                # Execute
                response = await reply_listener(Body='hello', From='+1234567890')

                # Assert
                mock_user_svc.update_user.assert_called()
                update_data = mock_user_svc.update_user.call_args[0][1]
                self.assertTrue(update_data['awaiting_event_id'])
                mock_send.assert_called_once()
                message = mock_send.call_args[0][1]
                self.assertIn('event ID', message)
                self.assertEqual(response.status_code, 200)


class TestListenerModeExtraQuestions(unittest.IsolatedAsyncioTestCase):
    """Test cases for extra questions handling."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.extract_name_with_llm')
    async def test_extra_question_name_extraction(self, mock_extract_name, mock_send,
                                                  mock_part_svc, mock_event_svc, mock_user_svc):
        """Test name extraction from extra questions."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': True,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_ordered_extra_questions.return_value = (
            {
                'name': {'id': 'extract_name_with_llm', 'text': 'What is your name?', 'order': 1},
                'age': {'id': 'extract_age_with_llm', 'text': 'What is your age?', 'order': 2}
            },
            ['name', 'age']
        )
        mock_part_svc.get_participant.return_value = {}
        mock_extract_name.return_value = 'John Doe'

        # Execute
        response = await reply_listener(Body='My name is John Doe', From='+1234567890')

        # Assert
        mock_extract_name.assert_called_once_with('My name is John Doe', 'test123')
        mock_part_svc.update_participant.assert_called_once_with('test123', '1234567890', {'name': 'John Doe', 'name': 'John Doe'})
        mock_user_svc.update_user.assert_called()
        # Should move to next question
        update_data = mock_user_svc.update_user.call_args[0][1]
        self.assertEqual(update_data['current_extra_question_index'], 1)
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.create_welcome_message')
    async def test_extra_questions_completion(self, mock_welcome, mock_send,
                                              mock_part_svc, mock_event_svc, mock_user_svc):
        """Test completion of all extra questions."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': True,
            'current_extra_question_index': 1,  # Last question
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_ordered_extra_questions.return_value = (
            {'age': {'id': 'extract_age_with_llm', 'text': 'What is your age?', 'order': 1}},
            ['age']
        )
        mock_part_svc.get_participant.return_value = {}
        mock_part_svc.get_participant_name.return_value = 'John Doe'
        mock_welcome.return_value = 'Welcome John Doe!'

        with patch('app.handlers.ListenerMode.extract_age_with_llm') as mock_extract_age:
            mock_extract_age.return_value = '30'

            # Execute
            response = await reply_listener(Body='I am 30', From='+1234567890')

            # Assert
            # Should complete extra questions
            update_calls = [call[0][1] for call in mock_user_svc.update_user.call_args_list]
            # Find the call that sets awaiting_extra_questions to False
            completion_call = next((call for call in update_calls if 'awaiting_extra_questions' in call and not call['awaiting_extra_questions']), None)
            self.assertIsNotNone(completion_call)
            mock_welcome.assert_called_once_with('test123', participant_name='John Doe')
            self.assertEqual(response.status_code, 200)


class TestListenerModeEventChange(unittest.IsolatedAsyncioTestCase):
    """Test cases for event change functionality."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.event_id_valid')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_change_event_command(self, mock_send, mock_valid, mock_event_svc, mock_user_svc):
        """Test the 'change event' command."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_valid.return_value = True

        # Execute
        response = await reply_listener(Body='change event event2', From='+1234567890')

        # Assert
        mock_user_svc.update_user.assert_called()
        update_data = mock_user_svc.update_user.call_args[0][1]
        self.assertTrue(update_data['awaiting_event_change_confirmation'])
        self.assertEqual(update_data['new_event_id_pending'], 'event2')
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('confirm', message.lower())
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.event_id_valid')
    async def test_confirm_event_change(self, mock_valid, mock_send, mock_part_svc,
                                       mock_event_svc, mock_user_svc):
        """Test confirming an event change."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': True,
            'new_event_id_pending': 'event2',
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}]
        mock_valid.return_value = True
        mock_event_svc.get_initial_message.return_value = 'Welcome!'
        mock_event_svc.get_ordered_extra_questions.return_value = ({}, [])

        # Execute
        response = await reply_listener(Body='yes', From='+1234567890')

        # Assert
        mock_part_svc.initialize_participant.assert_called_once_with('event2', '1234567890')
        mock_user_svc.update_user.assert_called()
        update_data = mock_user_svc.update_user.call_args[0][1]
        self.assertEqual(update_data['current_event_id'], 'event2')
        self.assertFalse(update_data['awaiting_event_change_confirmation'])
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_cancel_event_change(self, mock_send, mock_event_svc, mock_user_svc):
        """Test canceling an event change."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'event1',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': True,
            'new_event_id_pending': 'event2',
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True

        # Execute
        response = await reply_listener(Body='no', From='+1234567890')

        # Assert
        mock_user_svc.update_user.assert_called()
        update_data = mock_user_svc.update_user.call_args[0][1]
        self.assertFalse(update_data['awaiting_event_change_confirmation'])
        self.assertIsNone(update_data['new_event_id_pending'])
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('cancelled', message.lower())
        self.assertEqual(response.status_code, 200)


class TestListenerModeNameChange(unittest.IsolatedAsyncioTestCase):
    """Test cases for name change functionality."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_change_name_command(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test the 'change name' command."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True

        # Execute
        response = await reply_listener(Body='change name Jane Smith', From='+1234567890')

        # Assert
        mock_part_svc.set_participant_name.assert_called_once_with('test123', '1234567890', 'Jane Smith')
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('Jane Smith', message)
        self.assertEqual(response.status_code, 200)


class TestListenerModeCompletion(unittest.IsolatedAsyncioTestCase):
    """Test cases for survey completion."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_finalize_command(self, mock_send, mock_event_svc, mock_user_svc):
        """Test the 'finalize' command."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.get_completion_message.return_value = 'Thank you for participating!'

        # Execute
        response = await reply_listener(Body='finalize', From='+1234567890')

        # Assert
        mock_event_svc.get_completion_message.assert_called_once_with('test123')
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertEqual(message, 'Thank you for participating!')
        self.assertEqual(response.status_code, 200)


class TestListenerModeSecondRound(unittest.IsolatedAsyncioTestCase):
    """Test cases for second-round deliberation."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.run_second_round_for_user')
    async def test_second_round_enabled(self, mock_run_2nd, mock_send, mock_part_svc,
                                       mock_event_svc, mock_user_svc):
        """Test second-round deliberation when enabled."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.is_second_round_enabled.return_value = True
        mock_run_2nd.return_value = 'Here is a claim to consider...'
        mock_part_svc.process_second_round_interaction.return_value = True

        # Execute
        response = await reply_listener(Body='I think policy X is important', From='+1234567890')

        # Assert
        mock_event_svc.is_second_round_enabled.assert_called_once_with('test123')
        mock_run_2nd.assert_called_once_with('test123', '1234567890', user_msg='I think policy X is important')
        mock_part_svc.process_second_round_interaction.assert_called_once()
        mock_send.assert_called_once_with('+1234567890', 'Here is a claim to consider...')
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.run_second_round_for_user')
    async def test_second_round_duplicate_message(self, mock_run_2nd, mock_send, mock_part_svc,
                                                  mock_event_svc, mock_user_svc):
        """Test that duplicate messages in second-round are not processed."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.is_second_round_enabled.return_value = True
        mock_run_2nd.return_value = 'Response'
        mock_part_svc.process_second_round_interaction.return_value = False  # Duplicate

        # Execute
        response = await reply_listener(Body='Same message', From='+1234567890')

        # Assert
        mock_send.assert_not_called()  # Should not send message for duplicate
        self.assertEqual(response.status_code, 200)


class TestListenerModeNormalConversation(unittest.IsolatedAsyncioTestCase):
    """Test cases for normal LLM conversation."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    @patch('app.handlers.ListenerMode.client')
    @patch('app.handlers.ListenerMode.generate_bot_instructions')
    @patch('app.handlers.ListenerMode.extract_text_from_messages')
    async def test_normal_conversation_flow(self, mock_extract_text, mock_gen_instr, mock_client,
                                           mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test normal conversation with LLM."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.is_second_round_enabled.return_value = False
        mock_event_svc.get_welcome_message.return_value = 'Welcome!'
        mock_part_svc.get_interaction_count.return_value = 10
        mock_gen_instr.return_value = 'Bot instructions'
        mock_extract_text.return_value = 'AI response'

        # Mock OpenAI client
        mock_thread = Mock()
        mock_thread.id = 'thread123'
        mock_client.beta.threads.create.return_value = mock_thread

        mock_run = Mock()
        mock_run.status = 'completed'
        mock_client.beta.threads.runs.create_and_poll.return_value = mock_run

        mock_messages = Mock()
        mock_client.beta.threads.messages.list.return_value = mock_messages

        # Execute
        response = await reply_listener(Body='Hello bot', From='+1234567890')

        # Assert
        mock_part_svc.initialize_participant.assert_called_once_with('test123', '1234567890')
        mock_part_svc.get_interaction_count.assert_called_once_with('test123', '1234567890')
        mock_client.beta.threads.create.assert_called_once()
        mock_part_svc.append_interaction.assert_called()
        mock_send.assert_called_once_with('+1234567890', 'AI response')
        self.assertEqual(response.status_code, 200)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    @patch('app.handlers.ListenerMode.ParticipantService')
    @patch('app.handlers.ListenerMode.send_message')
    async def test_interaction_limit_reached(self, mock_send, mock_part_svc, mock_event_svc, mock_user_svc):
        """Test that interaction limit is enforced."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.is_second_round_enabled.return_value = False
        mock_part_svc.get_interaction_count.return_value = 450  # At limit

        # Execute
        response = await reply_listener(Body='Hello', From='+1234567890')

        # Assert
        mock_send.assert_called_once()
        message = mock_send.call_args[0][1]
        self.assertIn('limit', message.lower())
        self.assertEqual(response.status_code, 200)


class TestListenerModeEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Test cases for edge cases and error scenarios."""

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    async def test_empty_body(self, mock_event_svc, mock_user_svc):
        """Test handling of empty message body."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = [{'event_id': 'test123', 'timestamp': '2024-01-01T10:00:00'}]
        mock_event_svc.event_exists.return_value = True
        mock_event_svc.is_second_round_enabled.return_value = False
        mock_event_svc.get_welcome_message.return_value = 'Welcome!'

        with patch('app.handlers.ListenerMode.generate_bot_instructions'):
            # Execute
            response = await reply_listener(Body='', From='+1234567890')

            # Assert
            self.assertEqual(response.status_code, 400)

    @patch('app.handlers.ListenerMode.UserTrackingService')
    @patch('app.handlers.ListenerMode.EventService')
    async def test_phone_number_normalization(self, mock_event_svc, mock_user_svc):
        """Test that phone numbers are properly normalized."""
        # Setup
        mock_user_svc.get_or_create_user.return_value = (Mock(), {
            'events': [],
            'current_event_id': None,
            'awaiting_event_id': False,
            'awaiting_event_change_confirmation': False,
            'last_inactivity_prompt': None,
            'awaiting_extra_questions': False,
            'current_extra_question_index': 0,
            'invalid_attempts': 0
        })
        mock_user_svc.deduplicate_events.return_value = []

        with patch('app.handlers.ListenerMode.extract_event_id_with_llm') as mock_extract:
            with patch('app.handlers.ListenerMode.event_id_valid') as mock_valid:
                mock_extract.return_value = None
                mock_valid.return_value = False

                # Execute with formatted phone number
                await reply_listener(Body='test', From='+1-234-567-8900')

                # Assert - should be normalized to 12345678900
                mock_user_svc.get_or_create_user.assert_called_once_with('12345678900')


if __name__ == '__main__':
    unittest.main()
