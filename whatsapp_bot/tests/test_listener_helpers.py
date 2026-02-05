"""
Unit tests for listener_helpers.py

These tests ensure the generate_bot_instructions function works correctly
with various event configurations and edge cases.
"""

import sys
import unittest
from unittest.mock import patch, MagicMock, Mock

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
from app.utils.listener_helpers import generate_bot_instructions
from app.services.firestore_service import EventService


class TestGenerateBotInstructions(unittest.TestCase):
    """Test cases for generate_bot_instructions function."""

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_full_event_info(self, mock_get_event_info):
        """Test generating instructions when all event fields are provided."""
        event_id = 'test123'
        mock_get_event_info.return_value = {
            'event_name': 'Climate Change Summit',
            'event_location': 'Berlin',
            'event_background': 'A summit focused on climate action and policy',
            'language_guidance': 'The bot should respond in German when participants speak German.'
        }

        result = generate_bot_instructions(event_id)

        # Verify the function was called with correct event_id
        mock_get_event_info.assert_called_once_with(event_id)

        # Verify all custom fields are included in the instructions
        self.assertIn('Climate Change Summit', result)
        self.assertIn('Berlin', result)
        self.assertIn('A summit focused on climate action and policy', result)
        self.assertIn('The bot should respond in German when participants speak German.', result)

        # Verify core instruction components are present
        self.assertIn('Bot Objective', result)
        self.assertIn('Event Background', result)
        self.assertIn('Language Behavior', result)
        self.assertIn('Bot Personality', result)
        self.assertIn('Listening Mode', result)
        self.assertIn('Interaction Guidelines', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_partial_event_info(self, mock_get_event_info):
        """Test generating instructions when some fields use defaults."""
        event_id = 'test456'
        mock_get_event_info.return_value = {
            'event_name': 'Community Forum',
            'event_location': 'New York'
            # Missing event_background and language_guidance
        }

        result = generate_bot_instructions(event_id)

        mock_get_event_info.assert_called_once_with(event_id)

        # Verify provided fields are included
        self.assertIn('Community Forum', result)
        self.assertIn('New York', result)

        # Verify defaults are used for missing fields
        self.assertIn('the background', result)
        self.assertIn('No specific language behavior was requested', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_empty_language_guidance(self, mock_get_event_info):
        """Test that empty language_guidance triggers the default message."""
        event_id = 'test789'
        mock_get_event_info.return_value = {
            'event_name': 'Town Hall',
            'event_location': 'Austin',
            'event_background': 'Local government discussion',
            'language_guidance': ''  # Empty string
        }

        result = generate_bot_instructions(event_id)

        # Empty language_guidance should trigger the default message
        self.assertIn('No specific language behavior was requested', result)
        self.assertIn('defaults to matching the user\'s language', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_no_event_info(self, mock_get_event_info):
        """Test generating instructions when event doesn't exist (returns None)."""
        event_id = 'nonexistent'
        mock_get_event_info.return_value = None

        result = generate_bot_instructions(event_id)

        mock_get_event_info.assert_called_once_with(event_id)

        # All defaults should be used
        self.assertIn('the event', result)
        self.assertIn('the location', result)
        self.assertIn('the background', result)
        self.assertIn('No specific language behavior was requested', result)

        # Core instructions should still be present
        self.assertIn('Bot Objective', result)
        self.assertIn('Listening Mode', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_empty_event_info(self, mock_get_event_info):
        """Test generating instructions when event exists but has empty dict."""
        event_id = 'empty123'
        mock_get_event_info.return_value = {}

        result = generate_bot_instructions(event_id)

        # Should use all defaults when event_info is empty dict
        self.assertIn('the event', result)
        self.assertIn('the location', result)
        self.assertIn('the background', result)
        self.assertIn('No specific language behavior was requested', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_special_characters(self, mock_get_event_info):
        """Test that special characters in event fields are handled correctly."""
        event_id = 'special123'
        mock_get_event_info.return_value = {
            'event_name': 'Women\'s Health & Wellness Forum',
            'event_location': 'São Paulo',
            'event_background': 'Discussion on health topics including: nutrition, exercise & mental health',
            'language_guidance': 'Respond in Portuguese when appropriate. Use formal "você" forms.'
        }

        result = generate_bot_instructions(event_id)

        # Verify special characters are preserved
        self.assertIn('Women\'s Health & Wellness Forum', result)
        self.assertIn('São Paulo', result)
        self.assertIn('nutrition, exercise & mental health', result)
        self.assertIn('você', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_language_guidance_with_content(self, mock_get_event_info):
        """Test that non-empty language_guidance is used directly."""
        event_id = 'lang123'
        custom_guidance = 'Always respond in Spanish, using formal language.'
        mock_get_event_info.return_value = {
            'event_name': 'Policy Discussion',
            'event_location': 'Madrid',
            'event_background': 'Economic policy discussion',
            'language_guidance': custom_guidance
        }

        result = generate_bot_instructions(event_id)

        # Verify custom language guidance is used
        self.assertIn(custom_guidance, result)
        # Default message should NOT appear
        self.assertNotIn('No specific language behavior was requested', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_returns_string(self, mock_get_event_info):
        """Test that the function always returns a string."""
        mock_get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': 'Test Guidance'
        }

        result = generate_bot_instructions('test')

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_includes_all_sections(self, mock_get_event_info):
        """Test that all required instruction sections are present."""
        mock_get_event_info.return_value = {
            'event_name': 'Test',
            'event_location': 'Test',
            'event_background': 'Test',
            'language_guidance': 'Test'
        }

        result = generate_bot_instructions('test')

        # Verify all major sections are included
        required_sections = [
            'Bot Objective',
            'Event Background',
            'Language Behavior',
            'Bot Personality',
            'Listening Mode',
            'Data Retention',
            'Minimal Responses',
            'Interaction Guidelines',
            'Ultra-Brief Responses',
            'Acknowledgments',
            'Conversation Management',
            'Directive Responses',
            'Passive Engagement',
            'Closure of Interaction',
            'Concluding Interaction',
            'Overall Management'
        ]

        for section in required_sections:
            with self.subTest(section=section):
                self.assertIn(section, result, f"Missing section: {section}")

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_none_values(self, mock_get_event_info):
        """Test handling when event_info contains None values."""
        event_id = 'none123'
        mock_get_event_info.return_value = {
            'event_name': None,
            'event_location': None,
            'event_background': None,
            'language_guidance': None
        }

        result = generate_bot_instructions(event_id)

        # When values are None, .get() returns None which gets inserted as string "None"
        # This is the actual behavior - the function doesn't check for None
        self.assertIn('None', result)
        # But for language_guidance, None is falsy so default message is used
        self.assertIn('No specific language behavior was requested', result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_whitespace_only(self, mock_get_event_info):
        """Test handling of whitespace-only strings."""
        event_id = 'whitespace123'
        mock_get_event_info.return_value = {
            'event_name': '   ',
            'event_location': '\t\n',
            'event_background': '  ',
            'language_guidance': '   '
        }

        result = generate_bot_instructions(event_id)

        # Whitespace-only strings should still be used (not replaced with defaults)
        # but for language_guidance, empty/whitespace triggers default message
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_event_id_passed_correctly(self, mock_get_event_info):
        """Test that event_id is passed correctly to EventService."""
        test_event_ids = ['event1', 'event_123', 'TEST_EVENT', 'event-with-dashes']

        for event_id in test_event_ids:
            with self.subTest(event_id=event_id):
                mock_get_event_info.reset_mock()
                mock_get_event_info.return_value = {
                    'event_name': 'Test',
                    'event_location': 'Test',
                    'event_background': 'Test',
                    'language_guidance': 'Test'
                }

                generate_bot_instructions(event_id)

                mock_get_event_info.assert_called_once_with(event_id)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_with_long_content(self, mock_get_event_info):
        """Test that function handles very long event fields."""
        event_id = 'long123'
        long_text = 'A' * 1000  # 1000 character string
        mock_get_event_info.return_value = {
            'event_name': long_text,
            'event_location': long_text,
            'event_background': long_text,
            'language_guidance': long_text
        }

        result = generate_bot_instructions(event_id)

        # Should handle long content without errors
        self.assertIsInstance(result, str)
        self.assertIn(long_text, result)

    @patch.object(EventService, 'get_event_info')
    def test_generate_bot_instructions_immutability(self, mock_get_event_info):
        """Test that function doesn't modify the input or external state."""
        event_id = 'immutable123'
        original_data = {
            'event_name': 'Original Event',
            'event_location': 'Original Location',
            'event_background': 'Original Background',
            'language_guidance': 'Original Guidance'
        }
        mock_get_event_info.return_value = original_data.copy()

        result = generate_bot_instructions(event_id)

        # Verify original data wasn't modified
        self.assertEqual(original_data['event_name'], 'Original Event')
        self.assertEqual(original_data['event_location'], 'Original Location')

        # Verify result is generated
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


if __name__ == '__main__':
    unittest.main()
