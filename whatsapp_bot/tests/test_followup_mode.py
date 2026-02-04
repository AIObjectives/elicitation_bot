"""
Comprehensive unit tests for FollowupMode.py

Tests cover:
- User tracking operations
- Event validation and retrieval
- Participant operations
- Inactivity handling
- Extra questions flow
- Event change operations
- Second round deliberation
- Normal conversation flow
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import Response

from app.handlers.FollowupMode import reply_followup


class TestUserTrackingOperations:
    """Test user tracking initialization and updates."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_new_user_initialization(self, mock_send, mock_event_service, mock_user_service):
        """Test that a new user is properly initialized."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),  # doc_ref
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
        response = await reply_followup(
            Body="Hello",
            From="+1234567890"
        )

        # Assert
        assert response.status_code == 200
        mock_user_service.get_or_create_user.assert_called_once_with('1234567890')
        mock_user_service.deduplicate_events.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_user_events_deduplication(self, mock_send, mock_event_service, mock_user_service):
        """Test that duplicate events are properly deduplicated."""
        # Setup with duplicate events
        duplicate_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'},
        ]

        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': duplicate_events,
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )

        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'}
        ]

        # Execute
        await reply_followup(Body="test", From="+1234567890")

        # Assert
        mock_user_service.deduplicate_events.assert_called_once_with(duplicate_events)
        mock_user_service.update_user_events.assert_called_once()


class TestEventValidation:
    """Test event validation and existence checks."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_invalid_event_prompts_for_new_id(self, mock_send, mock_event_service, mock_user_service):
        """Test that an invalid current event prompts user for new event ID."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'invalid_event', 'timestamp': '2024-01-01T10:00:00'}],
                'current_event_id': 'invalid_event',
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': None,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'invalid_event', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = False

        # Execute
        response = await reply_followup(Body="test", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_event_service.event_exists.assert_called_once_with('invalid_event')
        mock_user_service.update_user.assert_called_once()
        call_args = mock_user_service.update_user.call_args[0]
        assert call_args[1]['awaiting_event_id'] is True
        assert call_args[1]['current_event_id'] is None

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.extract_event_id_with_llm')
    @patch('app.handlers.FollowupMode.event_id_valid')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_valid_event_id_acceptance(self, mock_send, mock_participant_service,
                                             mock_valid, mock_extract, mock_event_service,
                                             mock_user_service):
        """Test that a valid event ID is accepted and processed."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
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
        mock_extract.return_value = 'valid_event'
        mock_valid.return_value = True
        mock_event_service.get_initial_message.return_value = "Welcome to the event"
        mock_event_service.get_ordered_extra_questions.return_value = ({}, [])
        mock_participant_service.get_participant_name.return_value = None

        with patch('app.handlers.FollowupMode.create_welcome_message') as mock_welcome:
            mock_welcome.return_value = "Welcome!"

            # Execute
            response = await reply_followup(Body="valid_event", From="+1234567890")

            # Assert
            assert response.status_code == 200
            mock_extract.assert_called_once_with("valid_event")
            mock_valid.assert_called_once_with('valid_event')
            mock_participant_service.initialize_participant.assert_called_once_with('valid_event', '1234567890')


class TestInactivityHandling:
    """Test inactivity detection and prompting."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_inactivity_prompt_sent(self, mock_send, mock_user_service):
        """Test that inactivity prompt is sent after 24 hours."""
        # Setup - user inactive for 25 hours
        old_timestamp = (datetime.utcnow() - timedelta(hours=25)).isoformat()

        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': old_timestamp}],
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
            {'event_id': 'event1', 'timestamp': old_timestamp}
        ]

        # Execute
        response = await reply_followup(Body="test", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_user_service.update_user.assert_called()
        call_args = mock_user_service.update_user.call_args[0]
        assert 'last_inactivity_prompt' in call_args[1]

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_valid_event_selection_after_inactivity(self, mock_send, mock_user_service):
        """Test user can select event after inactivity prompt."""
        # Setup
        old_prompt = (datetime.utcnow() - timedelta(hours=1)).isoformat()

        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [
                    {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
                    {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'}
                ],
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': old_prompt,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'}
        ]

        # Execute - user selects event 1
        response = await reply_followup(Body="1", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_user_service.update_user.assert_called()
        call_args = mock_user_service.update_user.call_args[0]
        assert call_args[1]['current_event_id'] == 'event1'
        assert call_args[1]['last_inactivity_prompt'] is None

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_invalid_event_selection_increments_attempts(self, mock_send, mock_user_service):
        """Test invalid event selection increments invalid attempts."""
        # Setup
        old_prompt = (datetime.utcnow() - timedelta(hours=1)).isoformat()

        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
                'current_event_id': None,
                'awaiting_event_id': False,
                'awaiting_event_change_confirmation': False,
                'last_inactivity_prompt': old_prompt,
                'awaiting_extra_questions': False,
                'current_extra_question_index': 0,
                'invalid_attempts': 0
            }
        )
        mock_user_service.deduplicate_events.return_value = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]

        # Execute - user selects invalid index
        response = await reply_followup(Body="99", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_user_service.update_user.assert_called()
        call_args = mock_user_service.update_user.call_args[0]
        assert call_args[1]['invalid_attempts'] == 1


class TestExtraQuestionsFlow:
    """Test extra questions handling."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.extract_name_with_llm')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_extra_question_name_extraction(self, mock_send, mock_extract_name,
                                                  mock_participant_service, mock_event_service,
                                                  mock_user_service):
        """Test that name is extracted and stored during extra questions."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]

        extra_questions = {
            'name': {
                'id': 'extract_name_with_llm',
                'text': 'What is your name?',
                'enabled': True,
                'order': 1
            }
        }
        mock_event_service.get_ordered_extra_questions.return_value = (
            extra_questions,
            ['name']
        )
        mock_event_service.event_exists.return_value = True
        mock_extract_name.return_value = 'John Doe'
        mock_participant_service.get_participant_name.return_value = 'John Doe'

        with patch('app.handlers.FollowupMode.create_welcome_message') as mock_welcome:
            mock_welcome.return_value = "Welcome John!"

            # Execute
            response = await reply_followup(Body="John Doe", From="+1234567890")

            # Assert
            assert response.status_code == 200
            mock_extract_name.assert_called_once_with("John Doe", 'event1')
            mock_participant_service.update_participant.assert_called()
            call_args = mock_participant_service.update_participant.call_args[0]
            assert call_args[2]['name'] == 'John Doe'

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_multiple_extra_questions_sequence(self, mock_send, mock_participant_service,
                                                     mock_event_service, mock_user_service):
        """Test that multiple extra questions are asked in sequence."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]

        extra_questions = {
            'name': {'id': None, 'text': 'What is your name?', 'enabled': True, 'order': 1},
            'age': {'id': None, 'text': 'What is your age?', 'enabled': True, 'order': 2}
        }
        mock_event_service.get_ordered_extra_questions.return_value = (
            extra_questions,
            ['name', 'age']
        )
        mock_event_service.event_exists.return_value = True

        # Execute - answer first question
        response = await reply_followup(Body="John", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_user_service.update_user.assert_called()
        # Should update index to 1
        call_args = mock_user_service.update_user.call_args[0]
        assert call_args[1]['current_extra_question_index'] == 1


class TestEventChangeOperations:
    """Test event change and confirmation flow."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.event_id_valid')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_change_event_prompts_confirmation(self, mock_send, mock_valid,
                                                     mock_event_service, mock_user_service):
        """Test that changing event prompts for confirmation."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_valid.return_value = True

        # Execute
        response = await reply_followup(Body="change event event2", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_user_service.update_user.assert_called()
        call_args = mock_user_service.update_user.call_args[0]
        assert call_args[1]['awaiting_event_change_confirmation'] is True
        assert call_args[1]['new_event_id_pending'] == 'event2'

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.event_id_valid')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_change_event_confirmation_yes(self, mock_send, mock_valid,
                                                 mock_participant_service, mock_event_service,
                                                 mock_user_service):
        """Test confirming event change with 'yes'."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_valid.return_value = True
        mock_event_service.get_initial_message.return_value = "Welcome to event2"
        mock_event_service.get_ordered_extra_questions.return_value = ({}, [])

        # Execute
        response = await reply_followup(Body="yes", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_participant_service.initialize_participant.assert_called_once_with('event2', '1234567890')
        mock_user_service.update_user.assert_called()
        call_args = mock_user_service.update_user.call_args[0]
        assert call_args[1]['current_event_id'] == 'event2'

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_change_name_command(self, mock_send, mock_participant_service, mock_user_service):
        """Test changing participant name."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]

        with patch('app.handlers.FollowupMode.EventService') as mock_event_service:
            mock_event_service.event_exists.return_value = True

            # Execute
            response = await reply_followup(Body="change name Jane Smith", From="+1234567890")

            # Assert
            assert response.status_code == 200
            mock_participant_service.set_participant_name.assert_called_once_with(
                'event1', '1234567890', 'Jane Smith'
            )


class TestCompletionFlow:
    """Test finalize/finish commands."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_finalize_command(self, mock_send, mock_event_service, mock_user_service):
        """Test finalize command sends completion message."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.get_completion_message.return_value = "Thank you for participating!"

        # Execute
        response = await reply_followup(Body="finalize", From="+1234567890")

        # Assert
        assert response.status_code == 200
        mock_event_service.get_completion_message.assert_called_once_with('event1')
        mock_send.assert_called()


class TestSecondRoundDeliberation:
    """Test second round deliberation flow."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.run_second_round_for_user')
    @patch('app.handlers.FollowupMode.send_message')
    @patch('app.handlers.FollowupMode.db')
    async def test_second_round_enabled_flow(self, mock_db, mock_send, mock_second_round,
                                            mock_participant_service, mock_event_service,
                                            mock_user_service):
        """Test that second round is triggered when enabled."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.is_second_round_enabled.return_value = True
        mock_event_service.get_welcome_message.return_value = "Welcome"
        mock_second_round.return_value = "Here's what others think..."

        # Mock Firestore transaction
        mock_transaction = Mock()
        mock_db.transaction.return_value = mock_transaction

        mock_doc_ref = Mock()
        mock_snap = Mock()
        mock_snap.exists = False
        mock_snap.to_dict.return_value = {}
        mock_doc_ref.get.return_value = mock_snap

        mock_collection = Mock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        with patch('app.handlers.FollowupMode.generate_bot_instructions') as mock_instructions:
            mock_instructions.return_value = "Instructions"

            # Execute
            response = await reply_followup(Body="I think X", From="+1234567890")

            # Assert
            assert response.status_code == 200
            mock_event_service.is_second_round_enabled.assert_called_once_with('event1')
            mock_second_round.assert_called_once()


class TestNormalConversationFlow:
    """Test normal conversation with LLM."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.client')
    @patch('app.handlers.FollowupMode.send_message')
    @patch('app.handlers.FollowupMode.extract_text_from_messages')
    async def test_normal_conversation_flow(self, mock_extract, mock_send, mock_client,
                                           mock_participant_service, mock_event_service,
                                           mock_user_service):
        """Test normal conversation flow with OpenAI."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.is_second_round_enabled.return_value = False
        mock_event_service.get_welcome_message.return_value = "Welcome!"
        mock_participant_service.get_interaction_count.return_value = 5

        # Mock OpenAI responses
        mock_thread = Mock()
        mock_thread.id = 'thread123'
        mock_client.beta.threads.create.return_value = mock_thread

        mock_run = Mock()
        mock_run.status = 'completed'
        mock_client.beta.threads.runs.create_and_poll.return_value = mock_run

        mock_extract.return_value = "That's an interesting point!"

        with patch('app.handlers.FollowupMode.generate_bot_instructions') as mock_instructions:
            mock_instructions.return_value = "Instructions"

            # Execute
            response = await reply_followup(Body="What do you think?", From="+1234567890")

            # Assert
            assert response.status_code == 200
            mock_participant_service.initialize_participant.assert_called_once()
            mock_participant_service.append_interaction.assert_called()
            assert mock_participant_service.append_interaction.call_count == 2  # message + response

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.ParticipantService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_interaction_limit_reached(self, mock_send, mock_participant_service,
                                            mock_event_service, mock_user_service):
        """Test that interaction limit is enforced."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.is_second_round_enabled.return_value = False
        mock_event_service.get_welcome_message.return_value = "Welcome!"
        mock_participant_service.get_interaction_count.return_value = 450  # At limit

        with patch('app.handlers.FollowupMode.generate_bot_instructions') as mock_instructions:
            mock_instructions.return_value = "Instructions"

            # Execute
            response = await reply_followup(Body="test", From="+1234567890")

            # Assert
            assert response.status_code == 200
            mock_send.assert_called_once()
            assert "interaction limit" in mock_send.call_args[0][1].lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.EventService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_empty_body_handling(self, mock_send, mock_event_service, mock_user_service):
        """Test handling of empty message body."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
            {
                'events': [{'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}],
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
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        mock_event_service.event_exists.return_value = True
        mock_event_service.is_second_round_enabled.return_value = False
        mock_event_service.get_welcome_message.return_value = "Welcome"

        with patch('app.handlers.FollowupMode.generate_bot_instructions') as mock_instructions:
            mock_instructions.return_value = "Instructions"

            # Execute
            response = await reply_followup(Body="", From="+1234567890")

            # Assert
            assert response.status_code == 400

    @pytest.mark.asyncio
    @patch('app.handlers.FollowupMode.UserTrackingService')
    @patch('app.handlers.FollowupMode.send_message')
    async def test_phone_number_normalization(self, mock_send, mock_user_service):
        """Test that phone numbers are properly normalized."""
        # Setup
        mock_user_service.get_or_create_user.return_value = (
            Mock(),
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
        response = await reply_followup(Body="test", From="+1-234-567-8900")

        # Assert - phone number should be normalized
        mock_user_service.get_or_create_user.assert_called_once_with('12345678900')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
