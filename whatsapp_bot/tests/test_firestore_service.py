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
            'awaiting_event_id': False,
            'phone': normalized_phone
        }

        # Mock query result document
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.reference = MagicMock()
        mock_doc_snapshot.to_dict.return_value = expected_data

        # Mock query that returns list of documents
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc_snapshot]

        # Mock the where().limit() chain
        mock_where = MagicMock()
        mock_where.limit.return_value = mock_query

        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_where
        mock_db.collection.return_value = mock_collection

        # Execute
        doc_ref, user_data = UserTrackingService.get_or_create_user(normalized_phone)

        # Assert
        self.assertEqual(user_data, expected_data)
        mock_db.collection.assert_called_with('user_event_tracking')
        mock_collection.where.assert_called_with('phone', '==', normalized_phone)

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

        # Mock existing event document
        mock_doc = MagicMock()
        mock_doc.exists = True

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = EventService.event_exists(event_id)

        self.assertTrue(result)
        # Event config is now the event document itself, not 'info' subdocument
        mock_db.collection.assert_called_once_with('elicitation_bot_events')
        mock_collection.document.assert_called_once_with(event_id)

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
        # Event info is now the event document itself
        mock_db.collection.assert_called_once_with('elicitation_bot_events')
        mock_collection.document.assert_called_once_with(event_id)

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
            'event_id': event_id,
            'phone': normalized_phone
        }

        # Mock query result document
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.to_dict.return_value = expected_data

        # Mock query that returns list of documents
        mock_query = MagicMock()
        mock_query.stream.return_value = [mock_doc_snapshot]

        # Mock the where().limit() chain
        mock_where = MagicMock()
        mock_where.limit.return_value = mock_query

        # Mock subcollection structure for query
        mock_participant_collection = MagicMock()
        mock_participant_collection.where.return_value = mock_where

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        result = ParticipantService.get_participant(event_id, normalized_phone)

        self.assertEqual(result, expected_data)
        self.assertEqual(result['name'], 'John Doe')
        # Verify correct collection structure and query
        mock_db.collection.assert_called_once_with('elicitation_bot_events')
        mock_participant_collection.where.assert_called_once_with('phone', '==', normalized_phone)

    @patch('app.services.firestore_service.UserTrackingService.get_user')
    @patch('app.services.firestore_service.db')
    def test_initialize_participant_new(self, mock_db, mock_get_user):
        """Test initializing a new participant."""
        event_id = 'test123'
        normalized_phone = '1234567890'
        user_uuid = 'uuid-123'

        # Mock user data with UUID
        mock_get_user.return_value = {'user_id': user_uuid, 'phone': normalized_phone}

        # Mock empty query result (no existing participant)
        mock_query = MagicMock()
        mock_query.stream.return_value = []

        mock_where = MagicMock()
        mock_where.limit.return_value = mock_query

        # Mock new participant document ref
        mock_doc_ref = MagicMock()

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.where.return_value = mock_where
        mock_participant_collection.document.return_value = mock_doc_ref

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        ParticipantService.initialize_participant(event_id, normalized_phone)

        # Should call set to create document with UUID
        mock_doc_ref.set.assert_called_once()
        call_args = mock_doc_ref.set.call_args[0][0]
        self.assertIsNone(call_args['name'])
        self.assertEqual(call_args['interactions'], [])
        self.assertEqual(call_args['event_id'], event_id)
        self.assertEqual(call_args['phone'], normalized_phone)
        self.assertEqual(call_args['participant_id'], user_uuid)

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
    def test_get_all_participants(self, mock_db):
        """Test streaming all participants for an event."""
        event_id = 'test123'

        # Mock participant documents
        mock_doc1 = MagicMock()
        mock_doc1.id = 'uuid-1'
        mock_doc1.exists = True

        mock_doc2 = MagicMock()
        mock_doc2.id = 'uuid-2'
        mock_doc2.exists = True

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.stream.return_value = iter([mock_doc1, mock_doc2])

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        # Execute
        result = ParticipantService.get_all_participants(event_id)
        docs = list(result)

        # Assertions
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].id, 'uuid-1')
        self.assertEqual(docs[1].id, 'uuid-2')
        mock_db.collection.assert_called_once_with('elicitation_bot_events')
        mock_event_collection.document.assert_called_once_with(event_id)
        mock_event_doc.collection.assert_called_once_with('participants')
        mock_participant_collection.stream.assert_called_once()

    @patch('app.services.firestore_service.db')
    def test_get_specific_participants(self, mock_db):
        """Test getting specific participants by UUID."""
        event_id = 'test123'
        participant_ids = ['uuid-1', 'uuid-2', 'uuid-3']

        # Mock participant documents
        mock_docs = []
        for i, pid in enumerate(participant_ids):
            mock_doc = MagicMock()
            mock_doc.id = pid
            mock_doc.exists = True
            mock_docs.append(mock_doc)

        # Mock document reference for each participant
        mock_doc_refs = []
        for mock_doc in mock_docs:
            mock_doc_ref = MagicMock()
            mock_doc_ref.get.return_value = mock_doc
            mock_doc_refs.append(mock_doc_ref)

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.document.side_effect = mock_doc_refs

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        # Execute
        result = ParticipantService.get_specific_participants(event_id, participant_ids)
        docs = list(result)

        # Assertions
        self.assertEqual(len(docs), 3)
        self.assertEqual(docs[0].id, 'uuid-1')
        self.assertEqual(docs[1].id, 'uuid-2')
        self.assertEqual(docs[2].id, 'uuid-3')
        self.assertEqual(mock_participant_collection.document.call_count, 3)

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

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_get_claim_source_reference_success(self, mock_get_info):
        """Test getting claim source reference with valid config."""
        mock_get_info.return_value = {
            'second_round_claims_source': {
                'collection': 'reports_collection',
                'document': 'report_doc_123'
            }
        }

        col, doc = ReportService.get_claim_source_reference('test_event')

        self.assertEqual(col, 'reports_collection')
        self.assertEqual(doc, 'report_doc_123')

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_get_claim_source_reference_no_info(self, mock_get_info):
        """Test error when event info doesn't exist."""
        mock_get_info.return_value = None

        with self.assertRaises(RuntimeError) as context:
            ReportService.get_claim_source_reference('test_event')

        self.assertIn("No 'info' in", str(context.exception))

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_get_claim_source_reference_missing_collection(self, mock_get_info):
        """Test error when collection is missing."""
        mock_get_info.return_value = {
            'second_round_claims_source': {
                'document': 'report_doc'
            }
        }

        with self.assertRaises(RuntimeError) as context:
            ReportService.get_claim_source_reference('test_event')

        self.assertIn("Missing collection/document", str(context.exception))

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_get_claim_source_reference_missing_document(self, mock_get_info):
        """Test error when document is missing."""
        mock_get_info.return_value = {
            'second_round_claims_source': {
                'collection': 'reports'
            }
        }

        with self.assertRaises(RuntimeError) as context:
            ReportService.get_claim_source_reference('test_event')

        self.assertIn("Missing collection/document", str(context.exception))

    @patch('app.services.firestore_service.EventService.get_event_info')
    def test_get_claim_source_reference_empty_source(self, mock_get_info):
        """Test error when second_round_claims_source is empty."""
        mock_get_info.return_value = {
            'second_round_claims_source': {}
        }

        with self.assertRaises(RuntimeError) as context:
            ReportService.get_claim_source_reference('test_event')

        self.assertIn("Missing collection/document", str(context.exception))

    @patch('app.services.firestore_service.db')
    def test_fetch_all_claim_texts_success(self, mock_db):
        """Test fetching claim texts successfully."""
        claims_data = {
            'claims': [
                {'text': 'Climate change is real', 'id': 1},
                {'text': 'Renewable energy is important', 'id': 2},
                {'text': '  Solar panels are effective  ', 'id': 3},
                {'text': '', 'id': 4},  # Empty text should be filtered
                {'text': None, 'id': 5},  # None text should be filtered
            ]
        }

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = claims_data

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = ReportService.fetch_all_claim_texts('reports', 'doc123')

        self.assertEqual(len(result), 3)
        self.assertIn('Climate change is real', result)
        self.assertIn('Renewable energy is important', result)
        self.assertIn('Solar panels are effective', result)  # Should be stripped
        self.assertNotIn('', result)

    @patch('app.services.firestore_service.db')
    def test_fetch_all_claim_texts_no_document(self, mock_db):
        """Test fetching claims when document doesn't exist."""
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = ReportService.fetch_all_claim_texts('reports', 'doc123')

        self.assertEqual(result, [])

    @patch('app.services.firestore_service.db')
    def test_fetch_all_claim_texts_no_claims_field(self, mock_db):
        """Test fetching claims when claims field is missing."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'metadata': {}}

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = ReportService.fetch_all_claim_texts('reports', 'doc123')

        self.assertEqual(result, [])

    @patch('app.services.firestore_service.db')
    def test_fetch_all_claim_texts_empty_claims(self, mock_db):
        """Test fetching claims when claims array is empty."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'claims': []}

        mock_doc_ref = MagicMock()
        mock_doc_ref.get.return_value = mock_doc

        mock_collection = MagicMock()
        mock_collection.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_collection

        result = ReportService.fetch_all_claim_texts('reports', 'doc123')

        self.assertEqual(result, [])

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_participant_summary_success(self, mock_get_participant):
        """Test getting participant summary successfully."""
        mock_get_participant.return_value = {
            'summary': 'User strongly supports environmental policies',
            'name': 'Test User'
        }

        result = ReportService.get_participant_summary('event123', '1234567890')

        self.assertEqual(result, 'User strongly supports environmental policies')

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_participant_summary_with_whitespace(self, mock_get_participant):
        """Test getting participant summary with extra whitespace."""
        mock_get_participant.return_value = {
            'summary': '  Summary with spaces  '
        }

        result = ReportService.get_participant_summary('event123', '1234567890')

        self.assertEqual(result, 'Summary with spaces')

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_participant_summary_empty_string(self, mock_get_participant):
        """Test getting participant summary when it's empty."""
        mock_get_participant.return_value = {
            'summary': ''
        }

        result = ReportService.get_participant_summary('event123', '1234567890')

        self.assertIsNone(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_participant_summary_none(self, mock_get_participant):
        """Test getting participant summary when it's None."""
        mock_get_participant.return_value = {
            'summary': None
        }

        result = ReportService.get_participant_summary('event123', '1234567890')

        self.assertIsNone(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_participant_summary_no_participant(self, mock_get_participant):
        """Test getting summary when participant doesn't exist."""
        mock_get_participant.return_value = None

        result = ReportService.get_participant_summary('event123', '1234567890')

        self.assertIsNone(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_get_participant_summary_missing_field(self, mock_get_participant):
        """Test getting summary when summary field is missing."""
        mock_get_participant.return_value = {
            'name': 'Test User'
        }

        result = ReportService.get_participant_summary('event123', '1234567890')

        self.assertIsNone(result)

    @patch('app.services.firestore_service.ParticipantService.update_participant')
    def test_set_perspective_claims(self, mock_update):
        """Test setting perspective claims."""
        agreeable = ['[0] Claim A', '[2] Claim C']
        opposing = ['[1] Claim B', '[3] Claim D']
        reason = 'User supports renewable energy initiatives'

        ReportService.set_perspective_claims(
            'event123',
            '1234567890',
            agreeable,
            opposing,
            reason
        )

        mock_update.assert_called_once_with(
            'event123',
            '1234567890',
            {
                'agreeable_claims': agreeable,
                'opposing_claims': opposing,
                'claim_selection_reason': reason
            }
        )

    @patch('app.services.firestore_service.ParticipantService.update_participant')
    def test_set_perspective_claims_empty_lists(self, mock_update):
        """Test setting perspective claims with empty lists."""
        ReportService.set_perspective_claims(
            'event123',
            '1234567890',
            [],
            [],
            'No claims available'
        )

        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        self.assertEqual(call_args[2]['agreeable_claims'], [])
        self.assertEqual(call_args[2]['opposing_claims'], [])

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_has_perspective_claims_true_agreeable(self, mock_get_participant):
        """Test has_perspective_claims returns True when agreeable claims exist."""
        mock_get_participant.return_value = {
            'agreeable_claims': ['claim1', 'claim2'],
            'opposing_claims': None
        }

        result = ReportService.has_perspective_claims('event123', '1234567890')

        self.assertTrue(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_has_perspective_claims_true_opposing(self, mock_get_participant):
        """Test has_perspective_claims returns True when opposing claims exist."""
        mock_get_participant.return_value = {
            'agreeable_claims': None,
            'opposing_claims': ['claim1']
        }

        result = ReportService.has_perspective_claims('event123', '1234567890')

        self.assertTrue(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_has_perspective_claims_true_both(self, mock_get_participant):
        """Test has_perspective_claims returns True when both exist."""
        mock_get_participant.return_value = {
            'agreeable_claims': ['claim1'],
            'opposing_claims': ['claim2']
        }

        result = ReportService.has_perspective_claims('event123', '1234567890')

        self.assertTrue(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_has_perspective_claims_false(self, mock_get_participant):
        """Test has_perspective_claims returns False when no claims exist."""
        mock_get_participant.return_value = {
            'name': 'Test User',
            'summary': 'Some summary'
        }

        result = ReportService.has_perspective_claims('event123', '1234567890')

        self.assertFalse(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_has_perspective_claims_false_empty_lists(self, mock_get_participant):
        """Test has_perspective_claims returns False with empty lists."""
        mock_get_participant.return_value = {
            'agreeable_claims': [],
            'opposing_claims': []
        }

        result = ReportService.has_perspective_claims('event123', '1234567890')

        self.assertFalse(result)

    @patch('app.services.firestore_service.ParticipantService.get_participant')
    def test_has_perspective_claims_no_participant(self, mock_get_participant):
        """Test has_perspective_claims returns False when participant doesn't exist."""
        mock_get_participant.return_value = None

        result = ReportService.has_perspective_claims('event123', '1234567890')

        self.assertFalse(result)

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_all(self, mock_db):
        """Test streaming all participants without filter."""
        # Mock participant snapshots
        mock_snap1 = MagicMock()
        mock_snap1.id = 'uuid-1'
        mock_snap2 = MagicMock()
        mock_snap2.id = 'uuid-2'
        mock_snap3 = MagicMock()
        mock_snap3.id = 'uuid-3'

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.stream.return_value = iter([mock_snap1, mock_snap2, mock_snap3])

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        result = list(ReportService.stream_event_participants('event123'))

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, 'uuid-1')
        self.assertEqual(result[1].id, 'uuid-2')
        self.assertEqual(result[2].id, 'uuid-3')
        mock_participant_collection.stream.assert_called_once()

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_filtered(self, mock_db):
        """Test streaming specific participants with only_for filter (by phone)."""
        phone1 = '1234567890'
        phone2 = '0987654321'

        # Mock query results for each phone
        mock_snap1 = MagicMock()
        mock_snap1.id = 'uuid-1'

        mock_snap2 = MagicMock()
        mock_snap2.id = 'uuid-2'

        # Mock queries for each phone number
        mock_query1 = MagicMock()
        mock_query1.stream.return_value = [mock_snap1]

        mock_query2 = MagicMock()
        mock_query2.stream.return_value = [mock_snap2]

        # Mock where().limit() chain
        mock_where1 = MagicMock()
        mock_where1.limit.return_value = mock_query1

        mock_where2 = MagicMock()
        mock_where2.limit.return_value = mock_query2

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.where.side_effect = [mock_where1, mock_where2]

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        result = list(ReportService.stream_event_participants('event123', [phone1, phone2]))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, 'uuid-1')
        self.assertEqual(result[1].id, 'uuid-2')
        # Should use queries, not stream
        mock_participant_collection.stream.assert_not_called()

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_filtered_nonexistent(self, mock_db):
        """Test streaming with filter that includes non-existent participant (by phone)."""
        phone1 = '1234567890'
        phone_nonexistent = '9999999999'

        # Mock query results
        mock_snap1 = MagicMock()
        mock_snap1.id = 'uuid-1'

        # First query returns a result, second returns empty
        mock_query1 = MagicMock()
        mock_query1.stream.return_value = [mock_snap1]

        mock_query2 = MagicMock()
        mock_query2.stream.return_value = []  # No results for nonexistent

        # Mock where().limit() chain
        mock_where1 = MagicMock()
        mock_where1.limit.return_value = mock_query1

        mock_where2 = MagicMock()
        mock_where2.limit.return_value = mock_query2

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.where.side_effect = [mock_where1, mock_where2]

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        result = list(ReportService.stream_event_participants('event123', [phone1, phone_nonexistent]))

        # Should only yield existing participant
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 'uuid-1')

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_empty_filter(self, mock_db):
        """Test streaming with empty only_for list (treated as None)."""
        # Mock participant snapshots
        mock_snap1 = MagicMock()
        mock_snap1.id = 'uuid-1'

        # Mock subcollection structure
        mock_participant_collection = MagicMock()
        mock_participant_collection.stream.return_value = iter([mock_snap1])

        mock_event_doc = MagicMock()
        mock_event_doc.collection.return_value = mock_participant_collection

        mock_event_collection = MagicMock()
        mock_event_collection.document.return_value = mock_event_doc
        mock_db.collection.return_value = mock_event_collection

        result = list(ReportService.stream_event_participants('event123', []))

        # Empty list is falsy, so it should stream all like None
        self.assertEqual(len(result), 1)
        mock_participant_collection.stream.assert_called_once()


if __name__ == '__main__':
    unittest.main()
