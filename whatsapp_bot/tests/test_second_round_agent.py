"""
Unit tests for second_round_agent.py

These tests verify the behavior of second-round deliberation functions,
including report metadata fetching, dynamic prompt retrieval, user context
handling, and reply generation.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any, Optional

# Mock config and dependencies before importing the module under test
sys.modules['config.config'] = MagicMock()
sys.modules['openai'] = MagicMock()

from app.deliberation.second_round_agent import (
    _fetch_report_metadata,
    _fetch_dynamic_prompt,
    _get_user_context,
    _build_reply,
    run_second_round_for_user
)


class TestFetchReportMetadata(unittest.TestCase):
    """Test cases for _fetch_report_metadata function."""

    @patch('app.deliberation.second_round_agent.ReportService')
    def test_fetch_report_metadata_success(self, mock_report_service):
        """Test successfully fetching report metadata."""
        event_id = 'test_event_123'
        expected_metadata = {
            'title': 'Test Report',
            'author': 'Test Author',
            'summary': 'Test summary content'
        }

        mock_report_service.get_report_metadata.return_value = expected_metadata

        result = _fetch_report_metadata(event_id)

        self.assertEqual(result, expected_metadata)
        mock_report_service.get_report_metadata.assert_called_once_with(event_id)

    @patch('app.deliberation.second_round_agent.ReportService')
    def test_fetch_report_metadata_empty(self, mock_report_service):
        """Test fetching metadata when none exists."""
        event_id = 'nonexistent_event'
        mock_report_service.get_report_metadata.return_value = {}

        result = _fetch_report_metadata(event_id)

        self.assertEqual(result, {})
        mock_report_service.get_report_metadata.assert_called_once_with(event_id)

    @patch('app.deliberation.second_round_agent.ReportService')
    def test_fetch_report_metadata_with_none(self, mock_report_service):
        """Test handling None return from service."""
        event_id = 'test_event'
        mock_report_service.get_report_metadata.return_value = None

        result = _fetch_report_metadata(event_id)

        self.assertIsNone(result)


class TestFetchDynamicPrompt(unittest.TestCase):
    """Test cases for _fetch_dynamic_prompt function."""

    @patch('app.deliberation.second_round_agent.EventService')
    def test_fetch_dynamic_prompt_with_custom_prompts(self, mock_event_service):
        """Test fetching custom system and user prompts."""
        event_id = 'test_event'
        expected_prompts = {
            'system_prompt': 'Custom system instructions',
            'user_prompt': 'Custom user template: {summary}'
        }

        mock_event_service.get_second_round_prompts.return_value = expected_prompts

        result = _fetch_dynamic_prompt(event_id)

        self.assertEqual(result, expected_prompts)
        mock_event_service.get_second_round_prompts.assert_called_once_with(event_id)

    @patch('app.deliberation.second_round_agent.EventService')
    def test_fetch_dynamic_prompt_empty_prompts(self, mock_event_service):
        """Test fetching prompts when none are configured."""
        event_id = 'test_event'
        mock_event_service.get_second_round_prompts.return_value = {
            'system_prompt': '',
            'user_prompt': ''
        }

        result = _fetch_dynamic_prompt(event_id)

        self.assertEqual(result, {'system_prompt': '', 'user_prompt': ''})

    @patch('app.deliberation.second_round_agent.EventService')
    def test_fetch_dynamic_prompt_missing_event(self, mock_event_service):
        """Test fetching prompts for non-existent event."""
        event_id = 'missing_event'
        mock_event_service.get_second_round_prompts.return_value = {}

        result = _fetch_dynamic_prompt(event_id)

        self.assertEqual(result, {})


class TestGetUserContext(unittest.TestCase):
    """Test cases for _get_user_context function."""

    @patch('app.deliberation.second_round_agent.ParticipantService')
    def test_get_user_context_complete_data(self, mock_participant_service):
        """Test retrieving complete user context."""
        event_id = 'test_event'
        phone = '1234567890'

        mock_second_round_data = {
            'summary': 'User believes in climate action',
            'agreeable_claims': ['Claim 1', 'Claim 2'],
            'opposing_claims': ['Opposing 1'],
            'claim_selection_reason': 'Based on previous interactions',
            'second_round_interactions': [
                {'message': 'What about renewable energy?'},
                {'response': 'Renewable energy is important because...'},
                {'message': 'Tell me more'}
            ],
            'second_round_intro_done': True
        }

        mock_participant_service.get_second_round_data.return_value = mock_second_round_data

        result = _get_user_context(event_id, phone, history_k=6)

        self.assertIsNotNone(result)
        summary, agreeable, opposing, reason, turns, intro_done = result

        self.assertEqual(summary, 'User believes in climate action')
        self.assertEqual(len(agreeable), 2)
        self.assertEqual(len(opposing), 1)
        self.assertEqual(reason, 'Based on previous interactions')
        self.assertEqual(len(turns), 3)
        self.assertTrue(intro_done)

        # Verify turn structure
        self.assertEqual(turns[0]['role'], 'user')
        self.assertEqual(turns[0]['text'], 'What about renewable energy?')
        self.assertEqual(turns[1]['role'], 'assistant')
        self.assertEqual(turns[2]['role'], 'user')

    @patch('app.deliberation.second_round_agent.ParticipantService')
    def test_get_user_context_limits_history(self, mock_participant_service):
        """Test that history is limited to history_k interactions."""
        event_id = 'test_event'
        phone = '1234567890'

        # Create 10 interactions
        interactions = []
        for i in range(10):
            interactions.append({'message': f'Message {i}'})
            interactions.append({'response': f'Response {i}'})

        mock_second_round_data = {
            'summary': 'Test summary',
            'agreeable_claims': ['Claim 1'],
            'opposing_claims': ['Opposing 1'],
            'claim_selection_reason': 'Test reason',
            'second_round_interactions': interactions,
            'second_round_intro_done': False
        }

        mock_participant_service.get_second_round_data.return_value = mock_second_round_data

        result = _get_user_context(event_id, phone, history_k=4)

        summary, agreeable, opposing, reason, turns, intro_done = result

        # Should only have last 4 turns (history_k=4)
        self.assertEqual(len(turns), 4)
        self.assertEqual(turns[0]['text'], 'Message 8')
        self.assertEqual(turns[-1]['text'], 'Response 9')

    @patch('app.deliberation.second_round_agent.ParticipantService')
    def test_get_user_context_no_data_returns_none(self, mock_participant_service):
        """Test that None is returned when participant has no data."""
        event_id = 'test_event'
        phone = '1234567890'

        mock_second_round_data = {
            'summary': None,
            'agreeable_claims': [],
            'opposing_claims': [],
            'claim_selection_reason': None,
            'second_round_interactions': [],
            'second_round_intro_done': False
        }

        mock_participant_service.get_second_round_data.return_value = mock_second_round_data
        mock_participant_service.get_participant.return_value = None

        result = _get_user_context(event_id, phone)

        self.assertIsNone(result)
        mock_participant_service.get_participant.assert_called_once_with(event_id, phone)

    @patch('app.deliberation.second_round_agent.ParticipantService')
    def test_get_user_context_empty_interactions(self, mock_participant_service):
        """Test handling empty interaction list."""
        event_id = 'test_event'
        phone = '1234567890'

        mock_second_round_data = {
            'summary': 'User summary',
            'agreeable_claims': ['Claim 1'],
            'opposing_claims': ['Opposing 1'],
            'claim_selection_reason': 'Reason',
            'second_round_interactions': [],
            'second_round_intro_done': False
        }

        mock_participant_service.get_second_round_data.return_value = mock_second_round_data

        result = _get_user_context(event_id, phone)

        summary, agreeable, opposing, reason, turns, intro_done = result

        self.assertEqual(len(turns), 0)
        self.assertFalse(intro_done)


class TestBuildReply(unittest.TestCase):
    """Test cases for _build_reply function."""

    @patch('app.deliberation.second_round_agent.client')
    @patch('app.deliberation.second_round_agent._fetch_dynamic_prompt')
    def test_build_reply_success(self, mock_fetch_prompt, mock_client):
        """Test successful reply generation."""
        user_msg = "What about solar energy?"
        event_id = 'test_event'
        summary = 'User supports renewable energy'
        agreeable = ['Solar is clean', 'Wind is efficient']
        opposing = ['Nuclear is reliable']
        metadata = {'title': 'Climate Report'}
        reason = 'Selected based on prior statements'
        recent_turns = [
            {'role': 'user', 'text': 'Tell me about climate'},
            {'role': 'assistant', 'text': 'Climate change is important'}
        ]
        intro_done = False

        mock_fetch_prompt.return_value = {
            'system_prompt': '',
            'user_prompt': ''
        }

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Solar energy is a great option because...'
        mock_client.chat.completions.create.return_value = mock_response

        result = _build_reply(
            user_msg, event_id, summary, agreeable, opposing,
            metadata, reason, recent_turns, intro_done
        )

        self.assertEqual(result, 'Solar energy is a great option because...')
        mock_client.chat.completions.create.assert_called_once()

    @patch('app.deliberation.second_round_agent.client')
    @patch('app.deliberation.second_round_agent._fetch_dynamic_prompt')
    def test_build_reply_with_custom_prompts(self, mock_fetch_prompt, mock_client):
        """Test reply generation with custom prompts."""
        user_msg = "Test message"
        event_id = 'test_event'

        custom_prompts = {
            'system_prompt': 'Custom system prompt',
            'user_prompt': 'Custom template: {user_msg}'
        }
        mock_fetch_prompt.return_value = custom_prompts

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Custom response'
        mock_client.chat.completions.create.return_value = mock_response

        result = _build_reply(
            user_msg, event_id, 'summary', [], [], {}, None, [], False
        )

        self.assertEqual(result, 'Custom response')

        # Verify custom system prompt was used
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        self.assertEqual(messages[0]['role'], 'system')
        self.assertEqual(messages[0]['content'], 'Custom system prompt')

    @patch('app.deliberation.second_round_agent.client')
    @patch('app.deliberation.second_round_agent._fetch_dynamic_prompt')
    def test_build_reply_hides_claims_after_intro(self, mock_fetch_prompt, mock_client):
        """Test that claims are hidden after intro is done."""
        user_msg = "Test"
        event_id = 'test_event'
        agreeable = ['Claim 1', 'Claim 2']
        opposing = ['Opposing 1']
        intro_done = True  # Intro already done

        mock_fetch_prompt.return_value = {'system_prompt': '', 'user_prompt': '{agree_block}{oppose_block}'}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Response'
        mock_client.chat.completions.create.return_value = mock_response

        result = _build_reply(
            user_msg, event_id, 'summary', agreeable, opposing,
            {}, None, [], intro_done
        )

        # Check that the user prompt contains hidden markers
        call_args = mock_client.chat.completions.create.call_args
        user_prompt = call_args[1]['messages'][1]['content']
        self.assertIn('(hidden—show only if user asks)', user_prompt)

    @patch('app.deliberation.second_round_agent.client')
    @patch('app.deliberation.second_round_agent._fetch_dynamic_prompt')
    def test_build_reply_api_error(self, mock_fetch_prompt, mock_client):
        """Test handling of API errors."""
        user_msg = "Test"
        event_id = 'test_event'

        mock_fetch_prompt.return_value = {'system_prompt': '', 'user_prompt': ''}
        mock_client.chat.completions.create.side_effect = Exception('API Error')

        result = _build_reply(
            user_msg, event_id, 'summary', [], [], {}, None, [], False
        )

        self.assertIsNone(result)

    @patch('app.deliberation.second_round_agent.client')
    @patch('app.deliberation.second_round_agent._fetch_dynamic_prompt')
    def test_build_reply_empty_response(self, mock_fetch_prompt, mock_client):
        """Test handling of empty API response."""
        user_msg = "Test"
        event_id = 'test_event'

        mock_fetch_prompt.return_value = {'system_prompt': '', 'user_prompt': ''}

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response

        result = _build_reply(
            user_msg, event_id, 'summary', ['claim'], ['opp'], {}, None, [], False
        )

        self.assertEqual(result, '')

    @patch('app.deliberation.second_round_agent.client')
    @patch('app.deliberation.second_round_agent._fetch_dynamic_prompt')
    def test_build_reply_truncates_long_history(self, mock_fetch_prompt, mock_client):
        """Test that long history snippets are truncated."""
        user_msg = "Test"
        event_id = 'test_event'

        # Create a very long turn
        long_text = 'a' * 300  # 300 characters
        recent_turns = [{'role': 'user', 'text': long_text}]

        mock_fetch_prompt.return_value = {
            'system_prompt': '',
            'user_prompt': '{history_block}'
        }

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Response'
        mock_client.chat.completions.create.return_value = mock_response

        result = _build_reply(
            user_msg, event_id, 'summary', [], [], {}, None, recent_turns, False
        )

        # Verify the history block was created and long text was truncated
        call_args = mock_client.chat.completions.create.call_args
        user_prompt = call_args[1]['messages'][1]['content']
        self.assertIn('Recent Dialogue', user_prompt)
        self.assertIn('…', user_prompt)  # Truncation marker


class TestRunSecondRoundForUser(unittest.TestCase):
    """Test cases for run_second_round_for_user function."""

    @patch('app.deliberation.second_round_agent.ParticipantService')
    @patch('app.deliberation.second_round_agent._build_reply')
    @patch('app.deliberation.second_round_agent._get_user_context')
    @patch('app.deliberation.second_round_agent._fetch_report_metadata')
    def test_run_second_round_success(self, mock_fetch_meta, mock_get_ctx,
                                      mock_build, mock_participant_service):
        """Test successful second round execution."""
        event_id = 'test_event'
        phone_number = '1234567890'
        user_msg = 'What about wind energy?'

        mock_fetch_meta.return_value = {'title': 'Climate Report'}
        mock_get_ctx.return_value = (
            'User summary',
            ['Agreeable 1'],
            ['Opposing 1'],
            'Reason',
            [],
            False
        )
        mock_build.return_value = 'Wind energy is effective because...'

        result = run_second_round_for_user(event_id, phone_number, user_msg)

        self.assertEqual(result, 'Wind energy is effective because...')
        mock_participant_service.update_participant.assert_called_once_with(
            event_id, phone_number, {'second_round_intro_done': True}
        )

    @patch('app.deliberation.second_round_agent.select_and_store_for_event')
    @patch('app.deliberation.second_round_agent.summarize_and_store')
    @patch('app.deliberation.second_round_agent.ParticipantService')
    @patch('app.deliberation.second_round_agent._build_reply')
    @patch('app.deliberation.second_round_agent._get_user_context')
    @patch('app.deliberation.second_round_agent._fetch_report_metadata')
    def test_run_second_round_warmup_missing_data(self, mock_fetch_meta, mock_get_ctx,
                                                   mock_build, mock_participant_service,
                                                   mock_summarize, mock_select):
        """Test warmup process when user lacks summary/claims."""
        event_id = 'test_event'
        phone_number = '1234567890'
        user_msg = 'Test message'

        mock_fetch_meta.return_value = {}

        # First call: missing summary
        # Second call: data is ready
        mock_get_ctx.side_effect = [
            (None, ['Agreeable'], ['Opposing'], 'Reason', [], False),
            ('User summary', ['Agreeable'], ['Opposing'], 'Reason', [], False)
        ]

        mock_build.return_value = 'Generated response'

        result = run_second_round_for_user(event_id, phone_number, user_msg)

        self.assertEqual(result, 'Generated response')

        # Verify warmup functions were called
        mock_summarize.assert_called_once_with(event_id, only_for=[phone_number])
        mock_select.assert_called_once_with(event_id, only_for=[phone_number])

        # Verify context was fetched twice (before and after warmup)
        self.assertEqual(mock_get_ctx.call_count, 2)

    @patch('app.deliberation.second_round_agent.ParticipantService')
    @patch('app.deliberation.second_round_agent._get_user_context')
    @patch('app.deliberation.second_round_agent._fetch_report_metadata')
    def test_run_second_round_no_context(self, mock_fetch_meta, mock_get_ctx,
                                         mock_participant_service):
        """Test when user context cannot be retrieved."""
        event_id = 'test_event'
        phone_number = '1234567890'

        mock_fetch_meta.return_value = {}
        mock_get_ctx.return_value = None  # No context available

        result = run_second_round_for_user(event_id, phone_number)

        self.assertIsNone(result)
        mock_participant_service.update_participant.assert_not_called()

    @patch('app.deliberation.second_round_agent.select_and_store_for_event')
    @patch('app.deliberation.second_round_agent.summarize_and_store')
    @patch('app.deliberation.second_round_agent.ParticipantService')
    @patch('app.deliberation.second_round_agent._get_user_context')
    @patch('app.deliberation.second_round_agent._fetch_report_metadata')
    def test_run_second_round_warmup_fails(self, mock_fetch_meta, mock_get_ctx,
                                           mock_participant_service,
                                           mock_summarize, mock_select):
        """Test when warmup process still results in missing data."""
        event_id = 'test_event'
        phone_number = '1234567890'

        mock_fetch_meta.return_value = {}

        # Both calls return missing summary
        mock_get_ctx.side_effect = [
            (None, [], [], None, [], False),
            (None, [], [], None, [], False)
        ]

        result = run_second_round_for_user(event_id, phone_number)

        self.assertIsNone(result)

        # Verify warmup was attempted
        mock_summarize.assert_called_once()
        mock_select.assert_called_once()

        # Update should not be called since no reply was generated
        mock_participant_service.update_participant.assert_not_called()

    @patch('app.deliberation.second_round_agent.ParticipantService')
    @patch('app.deliberation.second_round_agent._build_reply')
    @patch('app.deliberation.second_round_agent._get_user_context')
    @patch('app.deliberation.second_round_agent._fetch_report_metadata')
    def test_run_second_round_build_reply_fails(self, mock_fetch_meta, mock_get_ctx,
                                                 mock_build, mock_participant_service):
        """Test when reply generation fails."""
        event_id = 'test_event'
        phone_number = '1234567890'

        mock_fetch_meta.return_value = {}
        mock_get_ctx.return_value = (
            'Summary', ['Agree'], ['Oppose'], 'Reason', [], False
        )
        mock_build.return_value = None  # Build fails

        result = run_second_round_for_user(event_id, phone_number)

        self.assertIsNone(result)
        mock_participant_service.update_participant.assert_not_called()

    @patch('app.deliberation.second_round_agent.ParticipantService')
    @patch('app.deliberation.second_round_agent._build_reply')
    @patch('app.deliberation.second_round_agent._get_user_context')
    @patch('app.deliberation.second_round_agent._fetch_report_metadata')
    def test_run_second_round_empty_message(self, mock_fetch_meta, mock_get_ctx,
                                            mock_build, mock_participant_service):
        """Test with empty user message."""
        event_id = 'test_event'
        phone_number = '1234567890'
        user_msg = ''

        mock_fetch_meta.return_value = {}
        mock_get_ctx.return_value = (
            'Summary', ['Agree'], ['Oppose'], 'Reason', [], False
        )
        mock_build.return_value = 'Reply with empty message'

        result = run_second_round_for_user(event_id, phone_number, user_msg)

        self.assertEqual(result, 'Reply with empty message')
        # Verify empty message was passed to build_reply
        mock_build.assert_called_once()
        call_args = mock_build.call_args[0]
        self.assertEqual(call_args[0], '')


if __name__ == '__main__':
    unittest.main()
