"""
Unit tests for the summarizer module.

These tests verify the functionality of the summarization and storage functions,
including message summarization via OpenAI and batch storage to Firestore.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List

# Mock config before any app imports
sys.modules['config.config'] = MagicMock()

from app.deliberation.summarizer import _summarize_user_messages, summarize_and_store


class TestSummarizeUserMessages(unittest.TestCase):
    """Test cases for _summarize_user_messages function."""

    @patch('app.deliberation.summarizer.client')
    def test_summarize_user_messages_success(self, mock_client):
        """Test successful summarization of user messages."""
        messages = [
            "I loved the event.",
            "The speakers were great.",
            "Very informative session."
        ]

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "User had a positive experience with great speakers."
        mock_client.chat.completions.create.return_value = mock_response

        result = _summarize_user_messages(messages)

        # Assertions
        self.assertEqual(result, "User had a positive experience with great speakers.")
        mock_client.chat.completions.create.assert_called_once()

        # Verify the call arguments
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs['model'], 'gpt-4o-mini')
        self.assertEqual(call_args.kwargs['max_tokens'], 300)
        self.assertEqual(call_args.kwargs['temperature'], 0.2)
        self.assertEqual(len(call_args.kwargs['messages']), 2)

    @patch('app.deliberation.summarizer.client')
    def test_summarize_empty_messages(self, mock_client):
        """Test summarization with empty message list."""
        messages = []

        result = _summarize_user_messages(messages)

        self.assertEqual(result, "No messages to summarize.")
        mock_client.chat.completions.create.assert_not_called()

    @patch('app.deliberation.summarizer.client')
    def test_summarize_none_messages(self, mock_client):
        """Test summarization with None in message list."""
        messages = ["First message", None, "Second message", "", "Third message"]

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary of messages."
        mock_client.chat.completions.create.return_value = mock_response

        result = _summarize_user_messages(messages)

        # Should still work, filtering out None and empty strings
        self.assertEqual(result, "Summary of messages.")
        mock_client.chat.completions.create.assert_called_once()

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_openai_error(self, mock_logger, mock_client):
        """Test error handling when OpenAI API fails."""
        messages = ["Test message"]

        # Mock OpenAI to raise an exception
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        result = _summarize_user_messages(messages)

        self.assertEqual(result, "⚠️ Error generating summary.")
        mock_logger.error.assert_called_once()

    @patch('app.deliberation.summarizer.client')
    def test_summarize_empty_response(self, mock_client):
        """Test handling of empty response from OpenAI."""
        messages = ["Test message"]

        # Mock OpenAI with empty response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response

        result = _summarize_user_messages(messages)

        self.assertEqual(result, "Summary unavailable.")

    @patch('app.deliberation.summarizer.client')
    def test_summarize_whitespace_only_response(self, mock_client):
        """Test handling of whitespace-only response from OpenAI."""
        messages = ["Test message"]

        # Mock OpenAI with whitespace response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "   \n\t  "
        mock_client.chat.completions.create.return_value = mock_response

        result = _summarize_user_messages(messages)

        self.assertEqual(result, "Summary unavailable.")

    @patch('app.deliberation.summarizer.client')
    def test_summarize_none_response(self, mock_client):
        """Test handling of None response from OpenAI."""
        messages = ["Test message"]

        # Mock OpenAI with None response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response

        result = _summarize_user_messages(messages)

        self.assertEqual(result, "Summary unavailable.")

    @patch('app.deliberation.summarizer.client')
    def test_summarize_long_messages(self, mock_client):
        """Test summarization with many long messages."""
        messages = [f"This is message number {i} with some content." for i in range(100)]

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary of 100 messages."
        mock_client.chat.completions.create.return_value = mock_response

        result = _summarize_user_messages(messages)

        self.assertEqual(result, "Summary of 100 messages.")
        mock_client.chat.completions.create.assert_called_once()


class TestSummarizeAndStore(unittest.TestCase):
    """Test cases for summarize_and_store function."""

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_success(self, mock_logger, mock_participant_service, mock_client):
        """Test successful summarization and storage of participant data."""
        event_id = "test_event_123"

        # Mock participant documents
        mock_participant1 = MagicMock()
        mock_participant1.exists = True
        mock_participant1.id = "participant1"
        mock_participant1.to_dict.return_value = {
            'interactions': [
                {'message': 'Hello'},
                {'message': 'This is great'}
            ],
            'summary': ''
        }

        mock_participant2 = MagicMock()
        mock_participant2.exists = True
        mock_participant2.id = "participant2"
        mock_participant2.to_dict.return_value = {
            'interactions': [
                {'message': 'Thanks'},
                {'message': 'Very helpful'}
            ],
            'summary': ''
        }

        # Mock info document (should be skipped)
        mock_info = MagicMock()
        mock_info.exists = True
        mock_info.id = "info"
        mock_info.to_dict.return_value = {'event_name': 'Test Event'}

        # Mock ParticipantService methods
        mock_participant_service.get_all_participants.return_value = [mock_participant1, mock_participant2, mock_info]
        mock_participant_service.batch_update_participants.return_value = 2

        # Mock OpenAI responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summarized content"
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 2)  # Two participants summarized
        mock_participant_service.get_all_participants.assert_called_once_with(event_id)
        mock_participant_service.batch_update_participants.assert_called_once()

        # Verify the updates passed to batch_update_participants
        call_args = mock_participant_service.batch_update_participants.call_args
        updates = call_args[0][1]  # Second argument is the updates list
        self.assertEqual(len(updates), 2)
        self.assertEqual(updates[0][0], "participant1")
        self.assertEqual(updates[1][0], "participant2")

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_skip_existing_summary(self, mock_logger, mock_participant_service, mock_client):
        """Test that participants with existing summaries are skipped."""
        event_id = "test_event_123"

        # Mock participant with existing summary
        mock_participant = MagicMock()
        mock_participant.exists = True
        mock_participant.id = "participant1"
        mock_participant.to_dict.return_value = {
            'interactions': [
                {'message': 'Hello'}
            ],
            'summary': 'Already has a summary'
        }

        # Mock ParticipantService
        mock_participant_service.get_all_participants.return_value = [mock_participant]

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 0)  # No participants updated
        mock_participant_service.batch_update_participants.assert_not_called()
        mock_client.chat.completions.create.assert_not_called()

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_skip_no_messages(self, mock_logger, mock_participant_service, mock_client):
        """Test that participants with no messages are skipped."""
        event_id = "test_event_123"

        # Mock participant with no interactions
        mock_participant = MagicMock()
        mock_participant.exists = True
        mock_participant.id = "participant1"
        mock_participant.to_dict.return_value = {
            'interactions': [],
            'summary': ''
        }

        # Mock ParticipantService
        mock_participant_service.get_all_participants.return_value = [mock_participant]

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 0)
        mock_participant_service.batch_update_participants.assert_not_called()
        mock_client.chat.completions.create.assert_not_called()

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_only_for_specific_participants(self, mock_logger, mock_participant_service, mock_client):
        """Test summarizing only specific participants."""
        event_id = "test_event_123"
        only_for = ["participant1", "participant2"]

        # Mock specific participant documents
        mock_participant1 = MagicMock()
        mock_participant1.exists = True
        mock_participant1.id = "participant1"
        mock_participant1.to_dict.return_value = {
            'interactions': [{'message': 'Hello'}],
            'summary': ''
        }

        mock_participant2 = MagicMock()
        mock_participant2.exists = True
        mock_participant2.id = "participant2"
        mock_participant2.to_dict.return_value = {
            'interactions': [{'message': 'Hi there'}],
            'summary': ''
        }

        # Mock ParticipantService
        mock_participant_service.get_specific_participants.return_value = [mock_participant1, mock_participant2]
        mock_participant_service.batch_update_participants.return_value = 2

        # Mock OpenAI responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summarized"
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        result = summarize_and_store(event_id, only_for=only_for)

        # Assertions
        self.assertEqual(result, 2)
        mock_participant_service.get_specific_participants.assert_called_once_with(event_id, list(only_for))
        mock_participant_service.batch_update_participants.assert_called_once()

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_skip_nonexistent_docs(self, mock_logger, mock_participant_service, mock_client):
        """Test that non-existent documents are skipped."""
        event_id = "test_event_123"

        # Mock non-existent document
        mock_participant = MagicMock()
        mock_participant.exists = False

        # Mock ParticipantService
        mock_participant_service.get_all_participants.return_value = [mock_participant]

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 0)
        mock_participant_service.batch_update_participants.assert_not_called()

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_filter_invalid_interactions(self, mock_logger, mock_participant_service, mock_client):
        """Test that invalid interactions are filtered out."""
        event_id = "test_event_123"

        # Mock participant with mixed valid/invalid interactions
        mock_participant = MagicMock()
        mock_participant.exists = True
        mock_participant.id = "participant1"
        mock_participant.to_dict.return_value = {
            'interactions': [
                {'message': 'Valid message 1'},
                'not a dict',  # Invalid
                {'response': 'Only response, no message'},  # No message field
                {'message': 'Valid message 2'},
                None,  # Invalid
            ],
            'summary': ''
        }

        # Mock ParticipantService
        mock_participant_service.get_all_participants.return_value = [mock_participant]
        mock_participant_service.batch_update_participants.return_value = 1

        # Mock OpenAI responses
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Summary of valid messages"
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 1)

        # Verify that only valid messages were passed to OpenAI
        call_args = mock_client.chat.completions.create.call_args
        user_message = call_args.kwargs['messages'][1]['content']
        self.assertIn('Valid message 1', user_message)
        self.assertIn('Valid message 2', user_message)
        self.assertNotIn('not a dict', user_message)

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_handles_none_dict(self, mock_logger, mock_participant_service, mock_client):
        """Test handling of None participant data."""
        event_id = "test_event_123"

        # Mock participant with None dict
        mock_participant = MagicMock()
        mock_participant.exists = True
        mock_participant.id = "participant1"
        mock_participant.to_dict.return_value = None

        # Mock ParticipantService
        mock_participant_service.get_all_participants.return_value = [mock_participant]

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 0)
        mock_participant_service.batch_update_participants.assert_not_called()

    @patch('app.deliberation.summarizer.client')
    @patch('app.deliberation.summarizer.ParticipantService')
    @patch('app.deliberation.summarizer.logger')
    def test_summarize_and_store_handles_none_interactions(self, mock_logger, mock_participant_service, mock_client):
        """Test handling of None interactions list."""
        event_id = "test_event_123"

        # Mock participant with None interactions
        mock_participant = MagicMock()
        mock_participant.exists = True
        mock_participant.id = "participant1"
        mock_participant.to_dict.return_value = {
            'interactions': None,
            'summary': ''
        }

        # Mock ParticipantService
        mock_participant_service.get_all_participants.return_value = [mock_participant]

        # Execute
        result = summarize_and_store(event_id)

        # Assertions
        self.assertEqual(result, 0)
        mock_participant_service.batch_update_participants.assert_not_called()


if __name__ == '__main__':
    unittest.main()
