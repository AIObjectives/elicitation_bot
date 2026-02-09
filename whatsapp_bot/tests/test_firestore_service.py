"""
Unit tests for the Firestore service abstraction layer.

These tests demonstrate how to test the database service layer
using mocks to avoid actual Firestore calls during testing.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Mock config before any app imports
sys.modules['config.config'] = MagicMock()

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
    def test_get_all_participants(self, mock_get_collection_name, mock_db):
        """Test streaming all participants for an event."""
        event_id = 'test123'
        collection_name = 'AOI_test123'
        mock_get_collection_name.return_value = collection_name

        # Mock participant documents
        mock_doc1 = MagicMock()
        mock_doc1.id = 'participant1'
        mock_doc1.exists = True

        mock_doc2 = MagicMock()
        mock_doc2.id = 'participant2'
        mock_doc2.exists = True

        mock_collection = MagicMock()
        mock_collection.stream.return_value = [mock_doc1, mock_doc2]
        mock_db.collection.return_value = mock_collection

        # Execute
        result = ParticipantService.get_all_participants(event_id)
        docs = list(result)

        # Assertions
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].id, 'participant1')
        self.assertEqual(docs[1].id, 'participant2')
        mock_get_collection_name.assert_called_once_with(event_id)
        mock_db.collection.assert_called_once_with(collection_name)
        mock_collection.stream.assert_called_once()

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    def test_get_specific_participants(self, mock_get_collection_name, mock_db):
        """Test getting specific participants by ID."""
        event_id = 'test123'
        collection_name = 'AOI_test123'
        participant_ids = ['participant1', 'participant2', 'participant3']
        mock_get_collection_name.return_value = collection_name

        # Mock participant documents
        mock_docs = []
        for i, pid in enumerate(participant_ids):
            mock_doc = MagicMock()
            mock_doc.id = pid
            mock_doc.exists = True
            mock_docs.append(mock_doc)

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.side_effect = mock_docs

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Execute
        result = ParticipantService.get_specific_participants(event_id, participant_ids)
        docs = list(result)

        # Assertions
        self.assertEqual(len(docs), 3)
        self.assertEqual(docs[0].id, 'participant1')
        self.assertEqual(docs[1].id, 'participant2')
        self.assertEqual(docs[2].id, 'participant3')
        mock_get_collection_name.assert_called_once_with(event_id)
        mock_db.collection.assert_called_once_with(collection_name)
        self.assertEqual(mock_collection.document.call_count, 3)

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    @patch('app.services.firestore_service.logger')
    def test_batch_update_participants_small_batch(self, mock_logger, mock_get_collection_name, mock_db):
        """Test batch updating participants with small batch (< 400)."""
        event_id = 'test123'
        collection_name = 'AOI_test123'
        mock_get_collection_name.return_value = collection_name

        # Prepare updates
        updates = [
            ('participant1', {'summary': 'Summary 1'}),
            ('participant2', {'summary': 'Summary 2'}),
            ('participant3', {'summary': 'Summary 3'}),
        ]

        # Mock collection and batch
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        # Execute
        result = ParticipantService.batch_update_participants(event_id, updates)

        # Assertions
        self.assertEqual(result, 3)
        self.assertEqual(mock_batch.set.call_count, 3)
        mock_batch.commit.assert_called_once()  # Only one commit for small batch
        mock_logger.info.assert_called_once()

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    @patch('app.services.firestore_service.logger')
    def test_batch_update_participants_large_batch(self, mock_logger, mock_get_collection_name, mock_db):
        """Test batch updating participants with large batch (> 400)."""
        event_id = 'test123'
        collection_name = 'AOI_test123'
        mock_get_collection_name.return_value = collection_name

        # Prepare 450 updates to test multiple commits
        updates = [(f'participant{i}', {'summary': f'Summary {i}'}) for i in range(450)]

        # Mock collection and batch
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        # Need two batches for 450 updates
        mock_batch1 = MagicMock()
        mock_batch2 = MagicMock()
        mock_db.batch.side_effect = [mock_batch1, mock_batch2]

        # Execute
        result = ParticipantService.batch_update_participants(event_id, updates)

        # Assertions
        self.assertEqual(result, 450)
        # First batch should have 400 sets, second should have 50
        self.assertEqual(mock_batch1.set.call_count, 400)
        self.assertEqual(mock_batch2.set.call_count, 50)
        # Both batches should be committed
        mock_batch1.commit.assert_called_once()
        mock_batch2.commit.assert_called_once()

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    @patch('app.services.firestore_service.logger')
    def test_batch_update_participants_custom_batch_size(self, mock_logger, mock_get_collection_name, mock_db):
        """Test batch updating with custom batch size."""
        event_id = 'test123'
        collection_name = 'AOI_test123'
        mock_get_collection_name.return_value = collection_name

        # Prepare 15 updates with batch size of 10
        updates = [(f'participant{i}', {'summary': f'Summary {i}'}) for i in range(15)]

        # Mock collection and batch
        mock_doc_ref = MagicMock()
        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        mock_batch1 = MagicMock()
        mock_batch2 = MagicMock()
        mock_db.batch.side_effect = [mock_batch1, mock_batch2]

        # Execute with custom batch size
        result = ParticipantService.batch_update_participants(event_id, updates, batch_size=10)

        # Assertions
        self.assertEqual(result, 15)
        # First batch should have 10 sets, second should have 5
        self.assertEqual(mock_batch1.set.call_count, 10)
        self.assertEqual(mock_batch2.set.call_count, 5)
        mock_batch1.commit.assert_called_once()
        mock_batch2.commit.assert_called_once()

    @patch('app.services.firestore_service.db')
    @patch('app.services.firestore_service.EventService.get_collection_name')
    @patch('app.services.firestore_service.logger')
    def test_batch_update_participants_empty_updates(self, mock_logger, mock_get_collection_name, mock_db):
        """Test batch updating with no updates."""
        event_id = 'test123'
        collection_name = 'AOI_test123'
        mock_get_collection_name.return_value = collection_name

        updates = []

        # Mock collection and batch
        mock_collection = MagicMock()
        mock_db.collection.return_value = mock_collection

        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        # Execute
        result = ParticipantService.batch_update_participants(event_id, updates)

        # Assertions
        self.assertEqual(result, 0)
        mock_batch.set.assert_not_called()
        mock_batch.commit.assert_not_called()


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
