"""
Unit tests for find_perspectives module.

Tests cover the perspective selection and storage functionality,
including OpenAI API calls, parsing logic, and Firestore operations.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from typing import List

# Mock config before any app imports
sys.modules['config.config'] = MagicMock()

from app.deliberation.find_perspectives import (
    _select_agreeable_opposing,
    _parse_selection,
    select_and_store_for_event
)


class TestSelectAgreeableOpposing(unittest.TestCase):
    """Test cases for _select_agreeable_opposing function."""

    @patch('app.deliberation.find_perspectives.client')
    def test_select_agreeable_opposing_success(self, mock_client):
        """Test successful claim selection with valid response."""
        summary = "I strongly support renewable energy initiatives."
        bank = [
            "Solar power is the future",
            "Coal mining should continue",
            "Wind energy is cost-effective",
            "Fossil fuels are necessary"
        ]

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "**Agreeable Claims:**\n"
            "- [0] Solar power is the future\n"
            "- [2] Wind energy is cost-effective\n\n"
            "**Opposing Claims:**\n"
            "- [1] Coal mining should continue\n"
            "- [3] Fossil fuels are necessary\n\n"
            "**Reason:** The user supports clean energy."
        )
        mock_client.chat.completions.create.return_value = mock_response

        # Execute
        result = _select_agreeable_opposing(summary, bank)

        # Assert
        self.assertIn("Agreeable Claims", result)
        self.assertIn("Opposing Claims", result)
        self.assertIn("Reason", result)
        mock_client.chat.completions.create.assert_called_once()

        # Verify call arguments
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs['model'], 'gpt-4o')
        self.assertEqual(call_args.kwargs['temperature'], 0.4)
        self.assertEqual(call_args.kwargs['max_tokens'], 1200)
        self.assertEqual(len(call_args.kwargs['messages']), 2)

    @patch('app.deliberation.find_perspectives.client')
    def test_select_agreeable_opposing_empty_summary(self, mock_client):
        """Test with empty summary string."""
        summary = ""
        bank = ["Claim 1", "Claim 2"]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "**Reason:** No summary provided."
        mock_client.chat.completions.create.return_value = mock_response

        result = _select_agreeable_opposing(summary, bank)

        # Should still make API call
        mock_client.chat.completions.create.assert_called_once()
        self.assertIsInstance(result, str)

    @patch('app.deliberation.find_perspectives.client')
    def test_select_agreeable_opposing_empty_bank(self, mock_client):
        """Test with empty claim bank."""
        summary = "Test summary"
        bank = []

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "No claims available."
        mock_client.chat.completions.create.return_value = mock_response

        result = _select_agreeable_opposing(summary, bank)

        mock_client.chat.completions.create.assert_called_once()
        self.assertIsInstance(result, str)

    @patch('app.deliberation.find_perspectives.client')
    def test_select_agreeable_opposing_none_response(self, mock_client):
        """Test when OpenAI returns None content."""
        summary = "Test summary"
        bank = ["Claim 1"]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response

        result = _select_agreeable_opposing(summary, bank)

        # Should return empty string
        self.assertEqual(result, "")

    @patch('app.deliberation.find_perspectives.client')
    def test_select_agreeable_opposing_formats_claims_correctly(self, mock_client):
        """Test that claims are formatted with indices."""
        summary = "Test"
        bank = ["First claim", "Second claim", "Third claim"]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Result"
        mock_client.chat.completions.create.return_value = mock_response

        _select_agreeable_opposing(summary, bank)

        # Check that the user prompt contains formatted claims
        call_args = mock_client.chat.completions.create.call_args
        user_message = call_args.kwargs['messages'][1]['content']

        self.assertIn("[0] First claim", user_message)
        self.assertIn("[1] Second claim", user_message)
        self.assertIn("[2] Third claim", user_message)


class TestParseSelection(unittest.TestCase):
    """Test cases for _parse_selection function."""

    def test_parse_selection_full_response(self):
        """Test parsing a complete, well-formatted response."""
        block = """
**Agreeable Claims:**
- [0] Solar power is the future
- [2] Wind energy is cost-effective

**Opposing Claims:**
- [1] Coal mining should continue
- [3] Fossil fuels are necessary

**Reason:** The user supports renewable energy.
"""
        agreeable, opposing, reason = _parse_selection(block)

        self.assertEqual(len(agreeable), 2)
        self.assertEqual(len(opposing), 2)
        self.assertIn("[0]", agreeable[0])
        self.assertIn("[1]", opposing[0])
        self.assertEqual(reason, "The user supports renewable energy.")

    def test_parse_selection_minimal_response(self):
        """Test parsing with minimal claims."""
        block = """
**Agreeable Claims:**
- [5] Single agreeable claim

**Opposing Claims:**
- [7] Single opposing claim

**Reason:** Test reason.
"""
        agreeable, opposing, reason = _parse_selection(block)

        self.assertEqual(len(agreeable), 1)
        self.assertEqual(len(opposing), 1)
        self.assertIn("[5]", agreeable[0])
        self.assertIn("[7]", opposing[0])
        self.assertEqual(reason, "Test reason.")

    def test_parse_selection_missing_reason(self):
        """Test parsing when reason is missing."""
        block = """
**Agreeable Claims:**
- [0] Claim one

**Opposing Claims:**
- [1] Claim two
"""
        agreeable, opposing, reason = _parse_selection(block)

        self.assertEqual(len(agreeable), 1)
        self.assertEqual(len(opposing), 1)
        self.assertEqual(reason, "No reason provided.")

    def test_parse_selection_empty_sections(self):
        """Test parsing with empty claim sections."""
        block = """
**Agreeable Claims:**

**Opposing Claims:**

**Reason:** No claims available.
"""
        agreeable, opposing, reason = _parse_selection(block)

        self.assertEqual(len(agreeable), 0)
        self.assertEqual(len(opposing), 0)
        self.assertEqual(reason, "No claims available.")

    def test_parse_selection_malformed_claims(self):
        """Test parsing with malformed claim lines."""
        block = """
**Agreeable Claims:**
- [0] Valid claim
- Invalid claim without brackets
- [2] Another valid claim

**Opposing Claims:**
- [5] Valid opposing
- Also invalid

**Reason:** Mixed format.
"""
        agreeable, opposing, reason = _parse_selection(block)

        # Only lines with "- [" and "]" should be captured
        self.assertEqual(len(agreeable), 2)
        self.assertEqual(len(opposing), 1)
        self.assertIn("[0]", agreeable[0])
        self.assertIn("[2]", agreeable[1])
        self.assertIn("[5]", opposing[0])

    def test_parse_selection_none_input(self):
        """Test parsing with None input."""
        agreeable, opposing, reason = _parse_selection(None)

        self.assertEqual(len(agreeable), 0)
        self.assertEqual(len(opposing), 0)
        self.assertEqual(reason, "No reason provided.")

    def test_parse_selection_empty_string(self):
        """Test parsing with empty string."""
        agreeable, opposing, reason = _parse_selection("")

        self.assertEqual(len(agreeable), 0)
        self.assertEqual(len(opposing), 0)
        self.assertEqual(reason, "No reason provided.")

    def test_parse_selection_extra_whitespace(self):
        """Test parsing handles extra whitespace correctly."""
        block = """
**Agreeable Claims:**
   - [0] Claim with spaces

**Opposing Claims:**
   - [1] Another claim

**Reason:**   Extra spaces here.
"""
        agreeable, opposing, reason = _parse_selection(block)

        self.assertEqual(len(agreeable), 1)
        self.assertEqual(len(opposing), 1)
        self.assertEqual(reason, "Extra spaces here.")

    def test_parse_selection_only_reason(self):
        """Test parsing when only reason is present."""
        block = "**Reason:** Just a reason, no claims."

        agreeable, opposing, reason = _parse_selection(block)

        self.assertEqual(len(agreeable), 0)
        self.assertEqual(len(opposing), 0)
        self.assertEqual(reason, "Just a reason, no claims.")


class TestSelectAndStoreForEvent(unittest.TestCase):
    """Test cases for select_and_store_for_event function."""

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    @patch('app.deliberation.find_perspectives._select_agreeable_opposing')
    def test_select_and_store_success(self, mock_select, mock_report_service, mock_logger):
        """Test successful processing of participants."""
        event_id = "test_event_123"

        # Mock claim source
        mock_report_service.get_claim_source_reference.return_value = ("claims_col", "claims_doc")
        mock_report_service.fetch_all_claim_texts.return_value = [
            "Claim 1", "Claim 2", "Claim 3", "Claim 4"
        ]

        # Mock participant snapshots
        mock_snap1 = MagicMock()
        mock_snap1.id = "user1"
        mock_snap2 = MagicMock()
        mock_snap2.id = "user2"

        mock_report_service.stream_event_participants.return_value = [mock_snap1, mock_snap2]

        # Mock has_perspective_claims - both participants need claims
        mock_report_service.has_perspective_claims.side_effect = [False, False]

        # Mock summaries
        mock_report_service.get_participant_summary.side_effect = [
            "User 1 likes renewable energy",
            "User 2 supports fossil fuels"
        ]

        # Mock LLM selection
        mock_select.side_effect = [
            "**Agreeable Claims:**\n- [0] Claim 1\n**Opposing Claims:**\n- [1] Claim 2\n**Reason:** Reason 1",
            "**Agreeable Claims:**\n- [2] Claim 3\n**Opposing Claims:**\n- [3] Claim 4\n**Reason:** Reason 2"
        ]

        # Execute
        result = select_and_store_for_event(event_id)

        # Assert
        self.assertEqual(result, 2)
        self.assertEqual(mock_report_service.set_perspective_claims.call_count, 2)

        # Verify first participant
        call1 = mock_report_service.set_perspective_claims.call_args_list[0]
        self.assertEqual(call1[0][0], event_id)
        self.assertEqual(call1[0][1], "user1")

        # Verify second participant
        call2 = mock_report_service.set_perspective_claims.call_args_list[1]
        self.assertEqual(call2[0][0], event_id)
        self.assertEqual(call2[0][1], "user2")

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    def test_select_and_store_empty_claim_bank(self, mock_report_service, mock_logger):
        """Test handling of empty claim bank."""
        event_id = "test_event"

        mock_report_service.get_claim_source_reference.return_value = ("col", "doc")
        mock_report_service.fetch_all_claim_texts.return_value = []

        result = select_and_store_for_event(event_id)

        self.assertEqual(result, 0)
        mock_logger.warning.assert_called_once()
        mock_report_service.stream_event_participants.assert_not_called()

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    def test_select_and_store_skip_info_document(self, mock_report_service, mock_logger):
        """Test that 'info' document is skipped."""
        event_id = "test_event"

        mock_report_service.get_claim_source_reference.return_value = ("col", "doc")
        mock_report_service.fetch_all_claim_texts.return_value = ["Claim 1"]

        # Mock info snapshot
        mock_info_snap = MagicMock()
        mock_info_snap.id = "info"

        mock_report_service.stream_event_participants.return_value = [mock_info_snap]

        result = select_and_store_for_event(event_id)

        self.assertEqual(result, 0)
        mock_report_service.has_perspective_claims.assert_not_called()

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    def test_select_and_store_skip_existing_claims(self, mock_report_service, mock_logger):
        """Test that participants with existing claims are skipped."""
        event_id = "test_event"

        mock_report_service.get_claim_source_reference.return_value = ("col", "doc")
        mock_report_service.fetch_all_claim_texts.return_value = ["Claim 1"]

        mock_snap = MagicMock()
        mock_snap.id = "user_with_claims"
        mock_report_service.stream_event_participants.return_value = [mock_snap]

        # Participant already has claims
        mock_report_service.has_perspective_claims.return_value = True

        result = select_and_store_for_event(event_id)

        self.assertEqual(result, 0)
        mock_report_service.get_participant_summary.assert_not_called()

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    def test_select_and_store_skip_empty_summary(self, mock_report_service, mock_logger):
        """Test that participants without summary are skipped."""
        event_id = "test_event"

        mock_report_service.get_claim_source_reference.return_value = ("col", "doc")
        mock_report_service.fetch_all_claim_texts.return_value = ["Claim 1"]

        mock_snap = MagicMock()
        mock_snap.id = "user_no_summary"
        mock_report_service.stream_event_participants.return_value = [mock_snap]

        mock_report_service.has_perspective_claims.return_value = False
        mock_report_service.get_participant_summary.return_value = None

        result = select_and_store_for_event(event_id)

        self.assertEqual(result, 0)
        mock_report_service.set_perspective_claims.assert_not_called()

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    @patch('app.deliberation.find_perspectives._select_agreeable_opposing')
    def test_select_and_store_with_only_for_filter(self, mock_select, mock_report_service, mock_logger):
        """Test processing specific participants with only_for parameter."""
        event_id = "test_event"
        only_for = ["user1", "user2"]

        mock_report_service.get_claim_source_reference.return_value = ("col", "doc")
        mock_report_service.fetch_all_claim_texts.return_value = ["Claim 1"]

        mock_snap1 = MagicMock()
        mock_snap1.id = "user1"
        mock_report_service.stream_event_participants.return_value = [mock_snap1]

        mock_report_service.has_perspective_claims.return_value = False
        mock_report_service.get_participant_summary.return_value = "Summary text"

        mock_select.return_value = (
            "**Agreeable Claims:**\n- [0] Claim\n"
            "**Opposing Claims:**\n- [1] Claim\n"
            "**Reason:** Test"
        )

        result = select_and_store_for_event(event_id, only_for=only_for)

        # Verify only_for was passed correctly
        mock_report_service.stream_event_participants.assert_called_once_with(
            event_id, ["user1", "user2"]
        )

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    def test_select_and_store_claim_source_error(self, mock_report_service, mock_logger):
        """Test handling of claim source reference error."""
        event_id = "test_event"

        mock_report_service.get_claim_source_reference.side_effect = RuntimeError(
            "Missing collection/document in second_round_claims_source"
        )

        with self.assertRaises(RuntimeError):
            select_and_store_for_event(event_id)

    @patch('app.deliberation.find_perspectives.logger')
    @patch('app.deliberation.find_perspectives.ReportService')
    @patch('app.deliberation.find_perspectives._select_agreeable_opposing')
    def test_select_and_store_mixed_participants(self, mock_select, mock_report_service, mock_logger):
        """Test processing with mix of valid, skipped, and info documents."""
        event_id = "test_event"

        mock_report_service.get_claim_source_reference.return_value = ("col", "doc")
        mock_report_service.fetch_all_claim_texts.return_value = ["Claim 1", "Claim 2"]

        # Mock various participant types
        info_snap = MagicMock()
        info_snap.id = "info"

        has_claims_snap = MagicMock()
        has_claims_snap.id = "user_with_claims"

        no_summary_snap = MagicMock()
        no_summary_snap.id = "user_no_summary"

        valid_snap = MagicMock()
        valid_snap.id = "valid_user"

        mock_report_service.stream_event_participants.return_value = [
            info_snap, has_claims_snap, no_summary_snap, valid_snap
        ]

        # Configure responses for each participant
        mock_report_service.has_perspective_claims.side_effect = [True, False, False]
        mock_report_service.get_participant_summary.side_effect = [None, "Valid summary"]

        mock_select.return_value = (
            "**Agreeable Claims:**\n- [0] Claim\n"
            "**Opposing Claims:**\n- [1] Claim\n"
            "**Reason:** Test"
        )

        result = select_and_store_for_event(event_id)

        # Only one valid participant should be processed
        self.assertEqual(result, 1)
        self.assertEqual(mock_report_service.set_perspective_claims.call_count, 1)

        call = mock_report_service.set_perspective_claims.call_args
        self.assertEqual(call[0][1], "valid_user")


if __name__ == '__main__':
    unittest.main()
