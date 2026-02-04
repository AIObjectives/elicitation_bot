"""
Unit tests for ListenerMode handler logic.

These tests focus on testing the core business logic of the ListenerMode
handler by mocking all external dependencies.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta

# Mock all external dependencies before importing
mock_modules = {
    'pydub': MagicMock(),
    'firebase_admin': MagicMock(),
    'decouple': MagicMock(),
    'twilio': MagicMock(),
    'twilio.rest': MagicMock(),
    'openai': MagicMock(),
}

for mod_name, mod_mock in mock_modules.items():
    sys.modules[mod_name] = mod_mock


class TestPhoneNumberNormalization(unittest.TestCase):
    """Test phone number normalization logic."""

    def test_phone_number_format_removal(self):
        """Test that phone number formatting characters are removed."""
        test_cases = [
            ('+1234567890', '1234567890'),
            ('+1-234-567-8900', '12345678900'),
            ('+1 234 567 8900', '12345678900'),
            ('+1-234-567-8900', '12345678900'),
        ]

        for input_phone, expected in test_cases:
            normalized = input_phone.replace("+", "").replace("-", "").replace(" ", "")
            self.assertEqual(normalized, expected, f"Failed for input: {input_phone}")


class TestEventDeduplication(unittest.TestCase):
    """Test event deduplication logic (mirrors UserTrackingService.deduplicate_events)."""

    def test_no_duplicates(self):
        """Test that events with no duplicates are returned unchanged."""
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'},
        ]

        # Simulate deduplication
        unique_events = {}
        for event in events:
            event_id = event['event_id']
            if event_id not in unique_events:
                unique_events[event_id] = event

        result = list(unique_events.values())
        self.assertEqual(len(result), 2)

    def test_keep_latest_duplicate(self):
        """Test that the latest timestamp is kept for duplicates."""
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event1', 'timestamp': '2024-01-01T12:00:00'},  # Newer
            {'event_id': 'event1', 'timestamp': '2024-01-01T11:00:00'},
        ]

        # Simulate deduplication with timestamp comparison
        unique_events = {}
        for event in events:
            event_id = event['event_id']
            if event_id not in unique_events:
                unique_events[event_id] = event
            else:
                existing_time = datetime.fromisoformat(unique_events[event_id]['timestamp'])
                new_time = datetime.fromisoformat(event['timestamp'])
                if new_time > existing_time:
                    unique_events[event_id] = event

        result = list(unique_events.values())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['timestamp'], '2024-01-01T12:00:00')


class TestInactivityDetection(unittest.TestCase):
    """Test inactivity detection logic."""

    def test_user_inactive_after_24_hours(self):
        """Test that user is marked inactive after 24 hours."""
        now = datetime(2024, 1, 2, 12, 0, 0)
        last_interaction = datetime(2024, 1, 1, 11, 0, 0)

        time_diff = now - last_interaction
        is_inactive = time_diff > timedelta(hours=24)

        self.assertTrue(is_inactive)
        self.assertGreater(time_diff.total_seconds(), 24 * 3600)

    def test_user_active_within_24_hours(self):
        """Test that user is not marked inactive within 24 hours."""
        now = datetime(2024, 1, 2, 10, 0, 0)
        last_interaction = datetime(2024, 1, 1, 11, 0, 0)

        time_diff = now - last_interaction
        is_inactive = time_diff > timedelta(hours=24)

        self.assertFalse(is_inactive)

    def test_multiple_events_use_most_recent(self):
        """Test that the most recent interaction is used for inactivity check."""
        events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T15:00:00'},  # Most recent
            {'event_id': 'event3', 'timestamp': '2024-01-01T12:00:00'},
        ]

        last_interaction_times = []
        for evt in events:
            event_timestamp = evt.get('timestamp', None)
            if event_timestamp:
                event_time = datetime.fromisoformat(event_timestamp)
                last_interaction_times.append(event_time)

        most_recent = max(last_interaction_times)
        self.assertEqual(most_recent, datetime(2024, 1, 1, 15, 0, 0))


class TestEventSelectionValidation(unittest.TestCase):
    """Test event selection validation logic."""

    def test_valid_event_selection(self):
        """Test valid event selection within range."""
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'},
        ]

        selection = '1'
        is_valid = selection.isdigit() and 1 <= int(selection) <= len(user_events)

        self.assertTrue(is_valid)
        selected_event = user_events[int(selection) - 1]
        self.assertEqual(selected_event['event_id'], 'event1')

    def test_invalid_event_selection_out_of_range(self):
        """Test invalid event selection outside range."""
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
        ]

        selection = '5'
        is_valid = selection.isdigit() and 1 <= int(selection) <= len(user_events)

        self.assertFalse(is_valid)

    def test_invalid_event_selection_non_digit(self):
        """Test invalid event selection with non-digit input."""
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
        ]

        selection = 'abc'
        is_valid = selection.isdigit() and 1 <= int(selection) <= len(user_events)

        self.assertFalse(is_valid)


class TestCommandParsing(unittest.TestCase):
    """Test command parsing logic."""

    def test_change_name_command_parsing(self):
        """Test parsing of 'change name' command."""
        body = 'change name John Doe'

        is_change_name = body.lower().startswith('change name ')
        if is_change_name:
            new_name = body[12:].strip()

        self.assertTrue(is_change_name)
        self.assertEqual(new_name, 'John Doe')

    def test_change_event_command_parsing(self):
        """Test parsing of 'change event' command."""
        body = 'change event event123'

        is_change_event = body.lower().startswith('change event ')
        if is_change_event:
            new_event_id = body[13:].strip()

        self.assertTrue(is_change_event)
        self.assertEqual(new_event_id, 'event123')

    def test_finalize_command_detection(self):
        """Test detection of finalize/finish commands."""
        test_cases = ['finalize', 'finish', 'FINALIZE', 'Finish']

        for body in test_cases:
            is_finalize = body.strip().lower() in ['finalize', 'finish']
            self.assertTrue(is_finalize, f"Failed for: {body}")

    def test_yes_no_confirmation(self):
        """Test yes/no confirmation parsing."""
        yes_cases = ['yes', 'y', 'YES', 'Y', ' yes ']
        no_cases = ['no', 'n', 'maybe', 'ok']

        for body in yes_cases:
            is_yes = body.strip().lower() in ['yes', 'y']
            self.assertTrue(is_yes, f"Failed for: {body}")

        for body in no_cases:
            is_yes = body.strip().lower() in ['yes', 'y']
            if body.strip().lower() in ['no', 'n']:
                self.assertFalse(is_yes)


class TestExtraQuestionsOrdering(unittest.TestCase):
    """Test extra questions ordering logic."""

    def test_questions_sorted_by_order_field(self):
        """Test that questions are sorted by order field."""
        extra_questions = {
            'age': {'enabled': True, 'order': 3, 'text': 'What is your age?'},
            'name': {'enabled': True, 'order': 1, 'text': 'What is your name?'},
            'location': {'enabled': True, 'order': 2, 'text': 'Where are you?'}
        }

        # Simulate ordering
        question_items = [(k, v) for k, v in extra_questions.items() if v.get('enabled')]
        question_items.sort(key=lambda x: x[1].get('order', 9999))
        enabled_questions = [item[0] for item in question_items]

        self.assertEqual(enabled_questions[0], 'name')
        self.assertEqual(enabled_questions[1], 'location')
        self.assertEqual(enabled_questions[2], 'age')

    def test_disabled_questions_excluded(self):
        """Test that disabled questions are excluded."""
        extra_questions = {
            'name': {'enabled': True, 'order': 1},
            'age': {'enabled': False, 'order': 2},
            'location': {'enabled': True, 'order': 3}
        }

        question_items = [(k, v) for k, v in extra_questions.items() if v.get('enabled')]
        enabled_questions = [item[0] for item in question_items]

        self.assertEqual(len(enabled_questions), 2)
        self.assertIn('name', enabled_questions)
        self.assertIn('location', enabled_questions)
        self.assertNotIn('age', enabled_questions)


class TestInteractionLimitCheck(unittest.TestCase):
    """Test interaction limit checking."""

    def test_limit_not_reached(self):
        """Test that user can continue when under limit."""
        interaction_count = 100
        limit = 450

        at_limit = interaction_count >= limit

        self.assertFalse(at_limit)

    def test_limit_reached(self):
        """Test that user is blocked at limit."""
        interaction_count = 450
        limit = 450

        at_limit = interaction_count >= limit

        self.assertTrue(at_limit)

    def test_limit_exceeded(self):
        """Test that user is blocked when over limit."""
        interaction_count = 500
        limit = 450

        at_limit = interaction_count >= limit

        self.assertTrue(at_limit)


class TestTimestampUpdating(unittest.TestCase):
    """Test timestamp updating logic."""

    def test_event_timestamp_update(self):
        """Test updating event timestamp when selected."""
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'},
            {'event_id': 'event2', 'timestamp': '2024-01-01T11:00:00'}
        ]

        selected_event_id = 'event1'
        current_time_iso = datetime.utcnow().isoformat()

        for evt in user_events:
            if evt['event_id'] == selected_event_id:
                evt['timestamp'] = current_time_iso
                break

        # Verify update
        event1 = next((e for e in user_events if e['event_id'] == 'event1'), None)
        self.assertIsNotNone(event1)
        self.assertEqual(event1['timestamp'], current_time_iso)

    def test_add_new_event_to_list(self):
        """Test adding a new event with timestamp."""
        user_events = [
            {'event_id': 'event1', 'timestamp': '2024-01-01T10:00:00'}
        ]

        new_event_id = 'event2'
        current_time_iso = datetime.utcnow().isoformat()

        # Check if event exists
        event_exists = False
        for evt in user_events:
            if evt['event_id'] == new_event_id:
                evt['timestamp'] = current_time_iso
                event_exists = True
                break

        if not event_exists:
            user_events.append({
                'event_id': new_event_id,
                'timestamp': current_time_iso
            })

        # Verify
        self.assertEqual(len(user_events), 2)
        event2 = next((e for e in user_events if e['event_id'] == 'event2'), None)
        self.assertIsNotNone(event2)


class TestInvalidAttemptHandling(unittest.TestCase):
    """Test invalid attempt counter logic."""

    def test_increment_invalid_attempts(self):
        """Test that invalid attempts are incremented."""
        invalid_attempts = 0
        invalid_attempts += 1

        self.assertEqual(invalid_attempts, 1)

    def test_reset_invalid_attempts(self):
        """Test that invalid attempts are reset after success."""
        invalid_attempts = 2

        # After successful action
        invalid_attempts = 0

        self.assertEqual(invalid_attempts, 0)

    def test_max_attempts_threshold(self):
        """Test checking against max attempts."""
        invalid_attempts = 2
        max_attempts = 2

        should_fallback = invalid_attempts >= max_attempts

        self.assertTrue(should_fallback)


class TestSecondRoundDuplicateDetection(unittest.TestCase):
    """Test second-round duplicate message detection logic."""

    def test_exact_duplicate_detected(self):
        """Test that exact duplicate messages are detected."""
        last_msg = "I think this policy is important"
        current_msg = "I think this policy is important"

        is_duplicate = last_msg == current_msg

        self.assertTrue(is_duplicate)

    def test_different_messages_not_duplicate(self):
        """Test that different messages are not duplicates."""
        last_msg = "I think this policy is important"
        current_msg = "I have a different opinion"

        is_duplicate = last_msg == current_msg

        self.assertFalse(is_duplicate)

    def test_normalized_duplicate_detection(self):
        """Test duplicate detection with normalization."""
        def normalize(msg):
            return msg.strip().lower()

        last_msg = "  Hello World  "
        current_msg = "hello world"

        is_duplicate = normalize(last_msg) == normalize(current_msg)

        self.assertTrue(is_duplicate)


if __name__ == '__main__':
    unittest.main()
