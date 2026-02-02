"""
Unit tests for the Firestore service abstraction layer.

These tests demonstrate how to test the database service layer
using mocks to avoid actual Firestore calls during testing.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from app.services.firestore_service import (
    UserTrackingService,
    EventService,
    ParticipantService,
    ReportService
)


class TestUserTrackingService(unittest.TestCase):
    """Test cases for UserTrackingService."""

    @patch('app.services.firestore_service.db')
    def test_get_or_create_user_existing(self, mock_db):
        """Test getting an existing user."""
        normalized_phone = '1234567890'
        expected_data = {
            'events': [{'event_id': 'test123', 'timestamp': '2024-01-01T00:00:00'}],
            'current_event_id': 'test123',
            'awaiting_event_id': False
        }

        # Mock Firestore document
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = expected_data

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Execute
        doc_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

        # Assert
        self.assertEqual(user_data, expected_data)
        mock_db.collection.assert_called_once_with('user_event_tracking')
        mock_collection.document.assert_called_once_with(normalized_phone)
        mock_doc_ref.set.assert_not_called()  # Should not create new doc

    @patch('app.services.firestore_service.db')
    def test_get_or_create_user_new(self, mock_db):
        """Test creating a new user."""
        normalized_phone = '9876543210'

        # Mock non-existent document
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Execute
        doc_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

        # Assert
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data['events'], [])
        self.assertIsNone(user_data['current_event_id'])
        self.assertFalse(user_data['awaiting_event_id'])
        mock_doc_ref.set.assert_called_once()

    def test_deduplicate_events(self):
        """Test event deduplication logic."""
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'},
            {'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'},  # Duplicate, newer
            {'event_id': 'event3', 'timestamp': '2024-01-01T13:00:00'},
        ]

        result = UserTrackingService.deduplicate_events(events)

        # Should have 3 unique events
        self.assertEqual(len(result), 3)

        # event1 should have the newer timestamp
        event1 = next((e for e in result if e['event_id'] == 'event1'), None)
        self.assertIsNotNone(event1)
        self.assertEqual(event1['timestamp'], '2024-01-01T12:00:00')

    def test_add_or_update_event_new(self):
        """Test adding a new event to events list."""
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        result = UserTrackingService.add_or_update_event(events, 'event2', timestamp)

        self.assertEqual(len(result), 2)
        event2 = next((e for e in result if e['event_id'] == 'event2'), None)
        self.assertIsNotNone(event2)
        self.assertEqual(event2['timestamp'], timestamp.isoformat())

    def test_add_or_update_event_existing(self):
        """Test updating an existing event timestamp."""
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]
        new_timestamp = datetime(2024, 1, 1, 15, 0, 0)

        result = UserTrackingService.add_or_update_event(events, 'event1', new_timestamp)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['timestamp'], new_timestamp.isoformat())


class TestEventService(unittest.TestCase):
    """Test cases for EventService."""

    @patch('app.services.firestore_service.db')
    def test_event_exists_true(self, mock_db):
        """Test checking if an event exists."""
        event_id = 'test123'

        # Mock existing info document
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = EventService.event_exists(event_id)

        self.assertTrue(result)
        mock_collection.document.assert_called_once_with('info')

    @patch('app.services.firestore_service.db')
    def test_get_event_info(self, mock_db):
        """Test getting event info."""
        event_id = 'test123'
        expected_info = {
            'mode': 'listener',
            'initial_message': 'Welcome!',
            'event_name': 'Test Event'
        }

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = expected_info

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = EventService.get_event_info(event_id)

        self.assertEqual(result, expected_info)
        self.assertEqual(result['mode'], 'listener')

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_is_second_round_enabled_true(self, mock_get_info):
        """Test checking if second round is enabled."""
        mock_get_info.return_value = {
            'second_round_claims_source': {
                'enabled': True,
                'collection': 'reports',
                'document': 'report123'
            }
        }

        result = EventService.is_second_round_enabled('test123')
        self.assertTrue(result)

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_is_second_round_enabled_legacy(self, mock_get_info):
        """Test backward compatibility with legacy field."""
        mock_get_info.return_value = {
            'second_deliberation_enabled': True
        }

        result = EventService.is_second_round_enabled('test123')
        self.assertTrue(result)

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_has_extra_questions_true(self, mock_get_info):
        """Test checking for extra questions."""
        mock_get_info.return_value = {
            'extra_questions': {
                'name': {'enabled': True, 'order': 1},
                'age': {'enabled': False, 'order': 2}
            }
        }

        result = EventService.has_extra_questions('test123')
        self.assertTrue(result)

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_get_ordered_extra_questions(self, mock_get_info):
        """Test getting ordered extra questions."""
        mock_get_info.return_value = {
            'extra_questions': {
                'age': {'enabled': True, 'order': 2, 'text': 'What is your age?'},
                'name': {'enabled': True, 'order': 1, 'text': 'What is your name?'},
                'location': {'enabled': False, 'order': 3, 'text': 'Where are you?'}
            }
        }

        questions, keys = EventService.get_ordered_extra_questions('test123')

        # Should only include enabled questions
        self.assertEqual(len(keys), 2)
        # Should be ordered correctly
        self.assertEqual(keys[0], 'name')
        self.assertEqual(keys[1], 'age')
        # Questions dict should contain both
        self.assertIn('name', questions)
        self.assertIn('age', questions)


class TestParticipantService(unittest.TestCase):
    """Test cases for ParticipantService."""

    @patch('app.services.firestore_service.db')
    def test_get_participant(self, mock_db):
        """Test getting participant data."""
        event_id = 'test123'
        normalized_phone = '1234567890'
        expected_data = {
            'name': 'John Doe',
            'interactions': [],
            'event_id': event_id
        }

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = expected_data

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = ParticipantService.get_participant(event_id, normalized_phone)

        self.assertEqual(result, expected_data)
        self.assertEqual(result['name'], 'John Doe')

    @patch('app.services.firestore_service.db')
    def test_initialize_participant_new(self, mock_db):
        """Test initializing a new participant."""
        event_id = 'test123'
        normalized_phone = '1234567890'

        # Mock non-existent document
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        ParticipantService.initialize_participant(event_id, normalized_phone)

        # Should call set to create document
        mock_doc_ref.set.assert_called_once()
        call_args = mock_doc_ref.set.call_args[0][0]
        self.assertIsNone(call_args['name'])
        self.assertEqual(call_args['interactions'], [])
        self.assertEqual(call_args['event_id'], event_id)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_interaction_count(self, mock_get_participant):
        """Test getting interaction count."""
        mock_get_participant.return_value = {
            'interactions': [
                {'message': 'msg1', 'response': 'resp1', 'ts': '2024-01-01T10:00:00'},
                {'message': 'msg2', 'response': 'resp2', 'ts': '2024-01-01T11:00:00'},
                {'message': 'msg3', 'response': 'resp3', 'ts': '2024-01-01T12:00:00'}
            ]
        }

        count = ParticipantService.get_interaction_count('test123', '1234567890')
        self.assertEqual(count, 3)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_survey_progress(self, mock_get_participant):
        """Test getting survey progress."""
        mock_get_participant.return_value = {
            'questions_asked': {'q1': True, 'q2': True},
            'responses': {'q1': 'answer1', 'q2': 'answer2'},
            'last_question_id': 2
        }

        progress = ParticipantService.get_survey_progress('test123', '1234567890')

        self.assertEqual(len(progress['questions_asked']), 2)
        self.assertEqual(len(progress['responses']), 2)
        self.assertEqual(progress['last_question_id'], 2)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_second_round_data(self, mock_get_participant):
        """Test getting second round data."""
        mock_get_participant.return_value = {
            'summary': 'User is concerned about policy X',
            'agreeable_claims': ['claim1', 'claim2'],
            'opposing_claims': ['claim3'],
            'second_round_intro_done': True
        }

        data = ParticipantService.get_second_round_data('test123', '1234567890')

        self.assertEqual(data['summary'], 'User is concerned about policy X')
        self.assertEqual(len(data['agreeable_claims']), 2)
        self.assertTrue(data['second_round_intro_done'])

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    def test_process_second_round_interaction_new(self, mock_get_collection, mock_db):
        """Test processing a new second-round interaction."""
        event_id = 'test123'
        normalized_phone = '1234567890'
        user_msg = 'I think this policy is important'
        sr_reply = 'Here is a relevant claim...'

        mock_get_collection.return_value = 'AOI_test123'

        # Mock document that doesn't exist yet
        mock_snap = MagicMock()
        mock_snap.exists = False

        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Mock transaction
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        # Execute
        result = ParticipantService.process_second_round_interaction(
            event_id,
            normalized_phone,
            user_msg,
            sr_reply
        )

        # Assert
        self.assertTrue(result)
        mock_get_collection.assert_called_once_with(event_id)
        mock_db.collection.assert_called_once_with('AOI_test123')
        mock_collection.document.assert_called_once_with(normalized_phone)

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    def test_process_second_round_interaction_duplicate(self, mock_get_collection, mock_db):
        """Test that duplicate messages are detected and skipped."""
        event_id = 'test123'
        normalized_phone = '1234567890'
        user_msg = 'Same message'

        mock_get_collection.return_value = 'AOI_test123'

        # Mock document with existing interactions
        mock_snap = MagicMock()
        mock_snap.exists = True
        mock_snap.to_dict.return_value = {
            'second_round_interactions': [
                {'message': 'Same message', 'ts': '2024-01-01T10:00:00'},
                {'response': 'Response', 'ts': '2024-01-01T10:00:01'}
            ]
        }

        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Mock transaction that returns the snapshot
        mock_transaction = MagicMock()

        def mock_transactional_func(func):
            """Mock the transactional decorator."""
            def wrapper(transaction, ref, msg, reply, norm_fn):
                # Simulate transaction behavior
                snap = mock_snap
                data = snap.to_dict() if snap.exists else {"second_round_interactions": []}
                interactions = data.get("second_round_interactions", [])

                # Check for duplicate
                last_user_msg = None
                for item in reversed(interactions):
                    if "message" in item:
                        last_user_msg = item["message"]
                        break

                if last_user_msg == msg:
                    return False

                return True

            return wrapper

        # Patch the transactional decorator
        with patch('app.services.firestore_service.firestore.transactional', mock_transactional_func):
            mock_db.transaction.return_value = mock_transaction

            # Execute
            result = ParticipantService.process_second_round_interaction(
                event_id,
                normalized_phone,
                user_msg,
                sr_reply=None
            )

            # Assert - should return False for duplicate
            self.assertFalse(result)

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    def test_process_second_round_interaction_with_normalization(self, mock_get_collection, mock_db):
        """Test duplicate detection with normalization function."""
        event_id = 'test123'
        normalized_phone = '1234567890'
        user_msg = '  Hello World  '

        def normalize_func(msg):
            return msg.strip().lower()

        mock_get_collection.return_value = 'AOI_test123'

        # Mock document with existing interactions
        mock_snap = MagicMock()
        mock_snap.exists = True
        mock_snap.to_dict.return_value = {
            'second_round_interactions': [
                {'message': 'hello world', 'ts': '2024-01-01T10:00:00'}
            ]
        }

        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Mock transaction
        mock_transaction = MagicMock()

        def mock_transactional_func(func):
            """Mock the transactional decorator with normalization."""
            def wrapper(transaction, ref, msg, reply, norm_fn):
                snap = mock_snap
                data = snap.to_dict() if snap.exists else {"second_round_interactions": []}
                interactions = data.get("second_round_interactions", [])

                last_user_msg = None
                for item in reversed(interactions):
                    if "message" in item:
                        last_user_msg = item["message"]
                        break

                # Use normalization if provided
                if last_user_msg and norm_fn:
                    if norm_fn(last_user_msg) == norm_fn(msg):
                        return False

                return True

            return wrapper

        with patch('app.services.firestore_service.firestore.transactional', mock_transactional_func):
            mock_db.transaction.return_value = mock_transaction

            # Execute
            result = ParticipantService.process_second_round_interaction(
                event_id,
                normalized_phone,
                user_msg,
                sr_reply=None,
                normalize_func=normalize_func
            )

            # Assert - should detect normalized duplicate
            self.assertFalse(result)

class TestReportService(unittest.TestCase):
    """Test cases for ReportService."""

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_second_round_config')
    def test_get_report_metadata(self, mock_get_config, mock_db):
        """Test getting report metadata."""
        mock_get_config.return_value = {
            'collection': 'reports',
            'document': 'report123'
        }

        expected_metadata = {
            'title': 'Community Report',
            'date': '2024-01-01',
            'claims_count': 25
        }

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'metadata': expected_metadata}

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = ReportService.get_report_metadata('test123')

        self.assertEqual(result, expected_metadata)
        mock_db.collection.assert_called_once_with('reports')
        mock_collection.document.assert_called_once_with('report123')


if __name__ == '__main__':
    unittest.main()
