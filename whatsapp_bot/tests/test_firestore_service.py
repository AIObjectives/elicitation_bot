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
        mock_snap1.id = 'user1'
        mock_snap2 = MagicMock()
        mock_snap2.id = 'user2'
        mock_snap3 = MagicMock()
        mock_snap3.id = 'info'

        mock_collection = MagicMock()
        mock_collection.stream.return_value = iter([mock_snap1, mock_snap2, mock_snap3])
        mock_db.collection.return_value = mock_collection

        result = list(ReportService.stream_event_participants('event123'))

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, 'user1')
        self.assertEqual(result[1].id, 'user2')
        self.assertEqual(result[2].id, 'info')
        mock_collection.stream.assert_called_once()

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_filtered(self, mock_db):
        """Test streaming specific participants with only_for filter."""
        # Mock specific participant snapshots
        mock_snap1 = MagicMock()
        mock_snap1.exists = True
        mock_snap1.id = 'user1'

        mock_snap2 = MagicMock()
        mock_snap2.exists = True
        mock_snap2.id = 'user3'

        mock_doc_ref1 = MagicMock()
        mock_doc_ref1.get.return_value = mock_snap1

        mock_doc_ref2 = MagicMock()
        mock_doc_ref2.get.return_value = mock_snap2

        mock_collection = MagicMock()
        mock_collection.document.side_effect = [mock_doc_ref1, mock_doc_ref2]
        mock_db.collection.return_value = mock_collection

        result = list(ReportService.stream_event_participants('event123', ['user1', 'user3']))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, 'user1')
        self.assertEqual(result[1].id, 'user3')
        mock_collection.stream.assert_not_called()

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_filtered_nonexistent(self, mock_db):
        """Test streaming with filter that includes non-existent participant."""
        # Mock existing and non-existing participants
        mock_snap1 = MagicMock()
        mock_snap1.exists = True
        mock_snap1.id = 'user1'

        mock_snap2 = MagicMock()
        mock_snap2.exists = False

        mock_doc_ref1 = MagicMock()
        mock_doc_ref1.get.return_value = mock_snap1

        mock_doc_ref2 = MagicMock()
        mock_doc_ref2.get.return_value = mock_snap2

        mock_collection = MagicMock()
        mock_collection.document.side_effect = [mock_doc_ref1, mock_doc_ref2]
        mock_db.collection.return_value = mock_collection

        result = list(ReportService.stream_event_participants('event123', ['user1', 'nonexistent']))

        # Should only yield existing participant
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 'user1')

    @patch('app.services.firestore_service.db')
    def test_stream_event_participants_empty_filter(self, mock_db):
        """Test streaming with empty only_for list (treated as None)."""
        # Mock participant snapshots
        mock_snap1 = MagicMock()
        mock_snap1.id = 'user1'

        mock_collection = MagicMock()
        mock_collection.stream.return_value = iter([mock_snap1])
        mock_db.collection.return_value = mock_collection

        result = list(ReportService.stream_event_participants('event123', []))

        # Empty list is falsy, so it should stream all like None
        self.assertEqual(len(result), 1)
        mock_collection.stream.assert_called_once()


if __name__ == '__main__':
    unittest.main()
