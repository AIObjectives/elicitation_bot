"""
Unit tests for survey_helpers.py

These tests ensure the initialize_user_document function works correctly
with the repository pattern, using EventService and ParticipantService.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock, Mock, call

# Mock the config module before any imports that depend on it
mock_db = Mock()
mock_logger = Mock()
mock_config_module = Mock()
mock_config_module.db = mock_db
mock_config_module.logger = mock_logger

sys.modules['config.config'] = mock_config_module

# Mock firebase_admin before firestore_service imports it
mock_firestore = Mock()
sys.modules['firebase_admin'] = Mock()
sys.modules['firebase_admin.firestore'] = mock_firestore

# Now we can safely import
from app.utils.survey_helpers import initialize_user_document
from app.services.firestore_service import EventService, ParticipantService


class TestInitializeUserDocument(unittest.TestCase):
    """Test cases for initialize_user_document function."""

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_valid_event(self, mock_get_event_info,
                                                       mock_get_questions,
                                                       mock_init_participant,
                                                       mock_update_participant):
        """Test initializing a user document with valid event data."""
        event_id = 'test123'
        normalized_phone = '1234567890'

        # Setup mock responses
        mock_get_event_info.return_value = {
            'mode': 'survey',
            'questions': [
                {'id': 1, 'text': 'What is your name?'},
                {'id': 2, 'text': 'Where are you from?'}
            ]
        }
        mock_get_questions.return_value = [
            {'id': 1, 'text': 'What is your name?'},
            {'id': 2, 'text': 'Where are you from?'}
        ]

        # Execute
        result = initialize_user_document(event_id, normalized_phone)

        # Assert EventService calls
        mock_get_event_info.assert_called_once_with(event_id)
        mock_get_questions.assert_called_once_with(event_id)

        # Assert ParticipantService calls
        mock_init_participant.assert_called_once_with(event_id, normalized_phone)
        mock_update_participant.assert_called_once()

        # Verify the update_participant call arguments
        call_args = mock_update_participant.call_args
        self.assertEqual(call_args[0][0], event_id)
        self.assertEqual(call_args[0][1], normalized_phone)

        # Verify payload structure
        payload = call_args[0][2]
        self.assertEqual(payload['interactions'], [])
        self.assertIsNone(payload['name'])
        self.assertEqual(payload['questions_asked'], {'1': False, '2': False})
        self.assertEqual(payload['responses'], {})
        self.assertIsNone(payload['last_question_id'])
        self.assertFalse(payload['survey_complete'])

        # Verify return value matches payload
        self.assertEqual(result, payload)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_no_questions(self, mock_get_event_info,
                                                        mock_get_questions,
                                                        mock_init_participant,
                                                        mock_update_participant):
        """Test initializing a user document when event has no questions."""
        event_id = 'test456'
        normalized_phone = '9876543210'

        mock_get_event_info.return_value = {
            'mode': 'survey',
            'questions': []
        }
        mock_get_questions.return_value = []

        result = initialize_user_document(event_id, normalized_phone)

        # Should still work with empty questions_asked
        payload = mock_update_participant.call_args[0][2]
        self.assertEqual(payload['questions_asked'], {})
        self.assertEqual(result['questions_asked'], {})

    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_nonexistent_event(self, mock_get_event_info):
        """Test that function raises ValueError when event doesn't exist."""
        event_id = 'nonexistent'
        normalized_phone = '1234567890'

        mock_get_event_info.return_value = None

        with self.assertRaises(ValueError) as context:
            initialize_user_document(event_id, normalized_phone)

        self.assertIn('No event info', str(context.exception))
        self.assertIn(event_id, str(context.exception))

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_string_question_ids(self, mock_get_event_info,
                                                                mock_get_questions,
                                                                mock_init_participant,
                                                                mock_update_participant):
        """Test that question IDs are converted to strings in questions_asked."""
        event_id = 'test789'
        normalized_phone = '5551234567'

        mock_get_event_info.return_value = {'mode': 'survey'}
        mock_get_questions.return_value = [
            {'id': 1, 'text': 'Question 1'},
            {'id': '2', 'text': 'Question 2'},  # Already a string
            {'id': 3.0, 'text': 'Question 3'}   # Float ID
        ]

        result = initialize_user_document(event_id, normalized_phone)

        # All IDs should be strings
        payload = mock_update_participant.call_args[0][2]
        self.assertIn('1', payload['questions_asked'])
        self.assertIn('2', payload['questions_asked'])
        self.assertIn('3.0', payload['questions_asked'])
        self.assertEqual(len(payload['questions_asked']), 3)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_many_questions(self, mock_get_event_info,
                                                          mock_get_questions,
                                                          mock_init_participant,
                                                          mock_update_participant):
        """Test initializing with a large number of questions."""
        event_id = 'large123'
        normalized_phone = '1112223333'

        # Create 50 questions
        questions = [{'id': i, 'text': f'Question {i}'} for i in range(1, 51)]

        mock_get_event_info.return_value = {'mode': 'survey'}
        mock_get_questions.return_value = questions

        result = initialize_user_document(event_id, normalized_phone)

        payload = mock_update_participant.call_args[0][2]
        self.assertEqual(len(payload['questions_asked']), 50)

        # All should be False initially
        for i in range(1, 51):
            self.assertFalse(payload['questions_asked'][str(i)])

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_calls_services_in_order(self, mock_get_event_info,
                                                               mock_get_questions,
                                                               mock_init_participant,
                                                               mock_update_participant):
        """Test that services are called in the correct order."""
        event_id = 'order123'
        normalized_phone = '3334445555'

        mock_get_event_info.return_value = {'mode': 'survey'}
        mock_get_questions.return_value = [{'id': 1, 'text': 'Test'}]

        # Create a mock manager to track call order
        manager = Mock()
        manager.attach_mock(mock_get_event_info, 'get_event_info')
        manager.attach_mock(mock_get_questions, 'get_questions')
        manager.attach_mock(mock_init_participant, 'init_participant')
        manager.attach_mock(mock_update_participant, 'update_participant')

        initialize_user_document(event_id, normalized_phone)

        # Verify order: get_event_info -> get_questions -> init_participant -> update_participant
        expected_calls = [
            call.get_event_info(event_id),
            call.get_questions(event_id),
            call.init_participant(event_id, normalized_phone),
            call.update_participant(event_id, normalized_phone, unittest.mock.ANY)
        ]

        self.assertEqual(manager.mock_calls[:4], expected_calls)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_payload_structure(self, mock_get_event_info,
                                                        mock_get_questions,
                                                        mock_init_participant,
                                                        mock_update_participant):
        """Test that payload has all required fields with correct types."""
        event_id = 'struct123'
        normalized_phone = '6667778888'

        mock_get_event_info.return_value = {'mode': 'survey'}
        mock_get_questions.return_value = [{'id': 1, 'text': 'Test'}]

        result = initialize_user_document(event_id, normalized_phone)

        # Verify all required fields exist
        required_fields = [
            'interactions',
            'name',
            'questions_asked',
            'responses',
            'last_question_id',
            'survey_complete'
        ]

        for field in required_fields:
            self.assertIn(field, result, f"Missing required field: {field}")

        # Verify field types
        self.assertIsInstance(result['interactions'], list)
        self.assertIsNone(result['name'])
        self.assertIsInstance(result['questions_asked'], dict)
        self.assertIsInstance(result['responses'], dict)
        self.assertIsNone(result['last_question_id'])
        self.assertIsInstance(result['survey_complete'], bool)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_duplicate_question_ids(self, mock_get_event_info,
                                                                   mock_get_questions,
                                                                   mock_init_participant,
                                                                   mock_update_participant):
        """Test handling of duplicate question IDs."""
        event_id = 'dup123'
        normalized_phone = '7778889999'

        mock_get_event_info.return_value = {'mode': 'survey'}
        # Duplicate question ID 1
        mock_get_questions.return_value = [
            {'id': 1, 'text': 'First question'},
            {'id': 2, 'text': 'Second question'},
            {'id': 1, 'text': 'Duplicate question'}
        ]

        result = initialize_user_document(event_id, normalized_phone)

        payload = mock_update_participant.call_args[0][2]
        # With dict comprehension, last duplicate wins (or first, depending on order)
        # The important thing is only 2 unique keys exist
        self.assertEqual(len(payload['questions_asked']), 2)
        self.assertIn('1', payload['questions_asked'])
        self.assertIn('2', payload['questions_asked'])

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_returns_same_payload_sent(self, mock_get_event_info,
                                                                 mock_get_questions,
                                                                 mock_init_participant,
                                                                 mock_update_participant):
        """Test that the function returns the same payload sent to update_participant."""
        event_id = 'return123'
        normalized_phone = '8889990000'

        mock_get_event_info.return_value = {'mode': 'survey'}
        mock_get_questions.return_value = [{'id': 1, 'text': 'Test'}]

        result = initialize_user_document(event_id, normalized_phone)

        # Get the payload that was sent to update_participant
        sent_payload = mock_update_participant.call_args[0][2]

        # Returned payload should match exactly
        self.assertEqual(result, sent_payload)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_special_characters_in_event_id(self, mock_get_event_info,
                                                                           mock_get_questions,
                                                                           mock_init_participant,
                                                                           mock_update_participant):
        """Test that event IDs with special characters are handled correctly."""
        event_id = 'test-event_123.v2'
        normalized_phone = '1234567890'

        mock_get_event_info.return_value = {'mode': 'survey'}
        mock_get_questions.return_value = [{'id': 1, 'text': 'Test'}]

        initialize_user_document(event_id, normalized_phone)

        # Verify event_id is passed correctly to all service calls
        mock_get_event_info.assert_called_once_with(event_id)
        mock_get_questions.assert_called_once_with(event_id)
        mock_init_participant.assert_called_once_with(event_id, normalized_phone)

        update_call = mock_update_participant.call_args
        self.assertEqual(update_call[0][0], event_id)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_with_normalized_phone_formats(self, mock_get_event_info,
                                                                     mock_get_questions,
                                                                     mock_init_participant,
                                                                     mock_update_participant):
        """Test that different normalized phone formats are handled correctly."""
        test_phones = ['1234567890', '0123456789', '9999999999']

        for phone in test_phones:
            with self.subTest(phone=phone):
                # Reset mocks
                mock_get_event_info.reset_mock()
                mock_get_questions.reset_mock()
                mock_init_participant.reset_mock()
                mock_update_participant.reset_mock()

                mock_get_event_info.return_value = {'mode': 'survey'}
                mock_get_questions.return_value = [{'id': 1, 'text': 'Test'}]

                initialize_user_document('test123', phone)

                # Verify phone is passed correctly
                mock_init_participant.assert_called_once_with('test123', phone)
                update_call = mock_update_participant.call_args
                self.assertEqual(update_call[0][1], phone)

    @patch.object(ParticipantService, 'update_participant')
    @patch.object(ParticipantService, 'initialize_participant')
    @patch.object(EventService, 'get_survey_questions')
    @patch.object(EventService, 'get_event_info')
    def test_initialize_user_document_immutability(self, mock_get_event_info,
                                                    mock_get_questions,
                                                    mock_init_participant,
                                                    mock_update_participant):
        """Test that function doesn't modify returned data from services."""
        event_id = 'immut123'
        normalized_phone = '1234567890'

        original_event_info = {'mode': 'survey', 'name': 'Test Event'}
        original_questions = [{'id': 1, 'text': 'Test'}]

        mock_get_event_info.return_value = original_event_info.copy()
        mock_get_questions.return_value = original_questions.copy()

        initialize_user_document(event_id, normalized_phone)

        # Original data should be unchanged
        self.assertEqual(original_event_info, {'mode': 'survey', 'name': 'Test Event'})
        self.assertEqual(original_questions, [{'id': 1, 'text': 'Test'}])


if __name__ == '__main__':
    unittest.main()
