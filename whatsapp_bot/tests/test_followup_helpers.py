"""
Unit tests for followup_helpers module.

These tests verify the generate_bot_instructions function which creates
dynamic bot instructions based on event details and user interactions.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

# Mock config before any app imports
sys.modules['config.config'] = MagicMock()

from app.utils.followup_helpers import generate_bot_instructions


class TestGenerateBotInstructions(unittest.TestCase):
    """Test cases for generate_bot_instructions function."""

    def setUp(self):
        """Set up common test fixtures."""
        self.event_id = 'test_event_123'
        self.normalized_phone = '1234567890'

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_happy_path_with_all_fields(self, mock_event_service, mock_participant_service):
        """Test generate_bot_instructions with complete event info and interactions."""
        # Mock complete event info
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Community Forum 2024',
            'event_location': 'San Francisco',
            'event_background': 'Annual community discussion',
            'language_guidance': 'Use English primarily, fallback to Spanish if needed',
            'bot_topic': 'Climate Change Policy',
            'bot_aim': 'Understand diverse perspectives on climate action',
            'bot_principles': [
                'Be respectful and inclusive',
                'Encourage critical thinking',
                'Avoid leading questions'
            ],
            'bot_personality': 'Friendly and curious',
            'bot_additional_prompts': [
                'Consider economic impacts',
                'Think about future generations'
            ],
            'follow_up_questions': {
                'enabled': True,
                'questions': [
                    'Can you tell me more about X?',
                    'What makes you feel that way about X?',
                    'Have you considered the perspective of X?'
                ]
            }
        }

        # Mock participant interactions
        mock_participant_service.get_participant.return_value = {
            'interactions': [
                {'message': 'I think climate change is important', 'response': 'Why do you think so?'},
                {'message': 'Because of rising temperatures', 'response': 'What impacts worry you most?'}
            ]
        }

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify the result is a string
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

        # Verify key information is included
        self.assertIn('Community Forum 2024', result)
        self.assertIn('San Francisco', result)
        self.assertIn('Climate Change Policy', result)
        self.assertIn('Friendly and curious', result)
        self.assertIn('Be respectful and inclusive', result)
        self.assertIn('Consider economic impacts', result)

        # Verify follow-up questions are included
        self.assertIn('Can you tell me more about X?', result)
        self.assertIn('What makes you feel that way about X?', result)

        # Verify past interactions are included
        self.assertIn('Bot: Why do you think so?', result)
        self.assertIn('User: I think climate change is important', result)

        # Verify language guidance is included
        self.assertIn('Use English primarily', result)

        # Verify services were called correctly
        mock_event_service.get_event_info.assert_called_once_with(self.event_id)
        mock_participant_service.get_participant.assert_called_once_with(
            self.event_id, self.normalized_phone
        )

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_no_event_info_uses_defaults(self, mock_event_service, mock_participant_service):
        """Test that defaults are used when event info is None."""
        # Mock no event info
        mock_event_service.get_event_info.return_value = None
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify defaults are used
        self.assertIn('the event', result)
        self.assertIn('the location', result)
        self.assertIn('the background', result)
        self.assertIn('No specialized follow-up questions are enabled', result)
        self.assertIn('No specific language behavior was requested', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_empty_event_info_fields(self, mock_event_service, mock_participant_service):
        """Test handling of empty strings and empty lists in event info."""
        # Mock event info with empty values
        mock_event_service.get_event_info.return_value = {
            'event_name': '',
            'event_location': '',
            'event_background': '',
            'language_guidance': '',
            'bot_topic': '',
            'bot_aim': '',
            'bot_principles': [],
            'bot_personality': '',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should still return valid instructions
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        self.assertIn('Elicitation bot', result)
        self.assertIn('No specialized follow-up questions', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_follow_up_questions_disabled(self, mock_event_service, mock_participant_service):
        """Test when follow-up questions exist but are disabled."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': [
                    'This should not appear',
                    'Neither should this'
                ]
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify follow-up questions are not included
        self.assertNotIn('This should not appear', result)
        self.assertIn('No specialized follow-up questions', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_follow_up_questions_enabled_but_empty(self, mock_event_service, mock_participant_service):
        """Test when follow-up questions are enabled but list is empty."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': True,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should show default message when no questions available
        self.assertIn('No specialized follow-up questions', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_no_participant_data(self, mock_event_service, mock_participant_service):
        """Test when participant has no data (new participant)."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should not have any past interactions
        self.assertNotIn('Bot: ', result.split('### Past User Interactions')[1].split('###')[0].strip())

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_participant_with_empty_interactions(self, mock_event_service, mock_participant_service):
        """Test when participant exists but has no interactions."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = {
            'interactions': []
        }

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should have empty past interactions section
        past_section = result.split('### Past User Interactions')[1].split('###')[0].strip()
        self.assertEqual(past_section, '')

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_interactions_with_missing_fields(self, mock_event_service, mock_participant_service):
        """Test handling of interactions with missing message or response fields."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = {
            'interactions': [
                {'message': 'Hello'},  # Missing response
                {'response': 'Hi there'},  # Missing message
                {'message': 'How are you?', 'response': 'I am good'}  # Complete
            ]
        }

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should only include the complete interaction
        self.assertIn('Bot: I am good', result)
        self.assertIn('User: How are you?', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_many_interactions_limited_to_30(self, mock_event_service, mock_participant_service):
        """Test that only last 30 interactions are included."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }

        # Create 50 interactions
        interactions = []
        for i in range(50):
            interactions.append({
                'message': f'User message {i}',
                'response': f'Bot response {i}'
            })

        mock_participant_service.get_participant.return_value = {
            'interactions': interactions
        }

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should include last 30 (20-49) but not first 20 (0-19)
        self.assertIn('User message 49', result)
        self.assertIn('User message 30', result)
        self.assertIn('User message 20', result)
        self.assertNotIn('User message 19', result)
        self.assertNotIn('User message 0', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_multiple_principles_formatting(self, mock_event_service, mock_participant_service):
        """Test that multiple principles are formatted correctly with bullets."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [
                'First principle',
                'Second principle',
                'Third principle'
            ],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify all principles are included with bullet formatting
        self.assertIn('- First principle', result)
        self.assertIn('- Second principle', result)
        self.assertIn('- Third principle', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_multiple_additional_prompts_formatting(self, mock_event_service, mock_participant_service):
        """Test that multiple additional prompts are formatted correctly."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [
                'Additional prompt one',
                'Additional prompt two'
            ],
            'follow_up_questions': {
                'enabled': False,
                'questions': []
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify all additional prompts are included
        self.assertIn('- Additional prompt one', result)
        self.assertIn('- Additional prompt two', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_follow_up_questions_enumeration(self, mock_event_service, mock_participant_service):
        """Test that follow-up questions are enumerated correctly."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': True,
                'questions': [
                    'First question about X?',
                    'Second question about Y?',
                    'Third question about Z?'
                ]
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify enumeration
        self.assertIn('1. First question about X?', result)
        self.assertIn('2. Second question about Y?', result)
        self.assertIn('3. Third question about Z?', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_special_characters_in_content(self, mock_event_service, mock_participant_service):
        """Test handling of special characters in event info and interactions."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event with "Quotes" & Symbols',
            'event_location': 'Location with <brackets>',
            'event_background': "Background with 'apostrophes'",
            'language_guidance': 'Use émojis 😊 and accénts',
            'bot_topic': 'Topic with $pecial ch@rs',
            'bot_aim': 'Aim with múltiple lañguages',
            'bot_principles': ['Principle with "nested" quotes'],
            'bot_personality': 'Personality: friendly & curious!',
            'bot_additional_prompts': [],
            'follow_up_questions': {
                'enabled': True,
                'questions': ['Question with symbols: @#$%?']
            }
        }
        mock_participant_service.get_participant.return_value = {
            'interactions': [
                {
                    'message': 'Message with <html> tags & symbols',
                    'response': 'Response with "quotes" and \'apostrophes\''
                }
            ]
        }

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify special characters are preserved
        self.assertIn('"Quotes" & Symbols', result)
        self.assertIn('<brackets>', result)
        self.assertIn("'apostrophes'", result)
        self.assertIn('émojis 😊', result)
        self.assertIn('$pecial ch@rs', result)
        self.assertIn('Question with symbols: @#$%?', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_missing_follow_up_questions_key(self, mock_event_service, mock_participant_service):
        """Test when follow_up_questions key is missing entirely."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': '',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': [],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': []
            # follow_up_questions key is missing
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Should use defaults and not crash
        self.assertIsInstance(result, str)
        self.assertIn('No specialized follow-up questions', result)

    @patch('app.utils.followup_helpers.ParticipantService')
    @patch('app.utils.followup_helpers.EventService')
    def test_result_structure_contains_all_sections(self, mock_event_service, mock_participant_service):
        """Test that the result contains all expected sections."""
        mock_event_service.get_event_info.return_value = {
            'event_name': 'Test Event',
            'event_location': 'Test Location',
            'event_background': 'Test Background',
            'language_guidance': 'Test Language',
            'bot_topic': 'Test Topic',
            'bot_aim': 'Test Aim',
            'bot_principles': ['Principle 1'],
            'bot_personality': 'Test Personality',
            'bot_additional_prompts': ['Prompt 1'],
            'follow_up_questions': {
                'enabled': True,
                'questions': ['Question 1']
            }
        }
        mock_participant_service.get_participant.return_value = None

        result = generate_bot_instructions(self.event_id, self.normalized_phone)

        # Verify all major sections are present
        self.assertIn('### Event Information', result)
        self.assertIn('Event Name:', result)
        self.assertIn('Event Location:', result)
        self.assertIn('Event Background:', result)
        self.assertIn('Language Behavior', result)
        self.assertIn('### Topic, Bot Objective, Conversation Principles, and Bot Personality', result)
        self.assertIn('**Topic**:', result)
        self.assertIn('**Aim**:', result)
        self.assertIn('**Principles**:', result)
        self.assertIn('**Personality**:', result)
        self.assertIn('### Past User Interactions', result)
        self.assertIn('### Additional Prompts', result)
        self.assertIn('### Follow-Up Questions and Instructions', result)
        self.assertIn('### Conversation Management', result)
        self.assertIn('### Final Notes', result)


if __name__ == '__main__':
    unittest.main()
