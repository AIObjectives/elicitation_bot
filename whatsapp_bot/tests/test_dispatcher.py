"""
Unit tests for the dispatcher module.

These tests verify that the dispatch_message function correctly routes
WhatsApp messages to the appropriate mode handler based on user state
and event configuration.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import pytest
from fastapi import HTTPException

from app.handlers.dispatcher import dispatch_message


class TestDispatchMessage(unittest.IsolatedAsyncioTestCase):
    """Test cases for dispatch_message function."""

    async def test_dispatch_to_listener_mode(self):
        """Test dispatching to listener mode handler."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123',
                'events': []
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'listener'
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Hello', '+1-234-567-8900', None)

            # Assert
            mock_user_service.get_user.assert_called_once_with('12345678900')
            mock_event_service.event_exists.assert_called_once_with('test123')
            mock_event_service.get_event_mode.assert_called_once_with('test123')
            mock_reply_listener.assert_called_once_with('Hello', '+1-234-567-8900', None)

    async def test_dispatch_to_followup_mode(self):
        """Test dispatching to followup mode handler."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_followup', new_callable=AsyncMock) as mock_reply_followup:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test456',
                'events': []
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'followup'
            mock_reply_followup.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('My response', '1234567890', None)

            # Assert
            mock_event_service.get_event_mode.assert_called_once_with('test456')
            mock_reply_followup.assert_called_once_with('My response', '1234567890', None)

    async def test_dispatch_to_survey_mode(self):
        """Test dispatching to survey mode handler."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_survey', new_callable=AsyncMock) as mock_reply_survey:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test789',
                'events': []
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'survey'
            mock_reply_survey.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Answer', '9876543210', None)

            # Assert
            mock_event_service.get_event_mode.assert_called_once_with('test789')
            mock_reply_survey.assert_called_once_with('Answer', '9876543210', None)

    async def test_dispatch_with_uppercase_mode(self):
        """Test that mode is case-insensitive (handles uppercase)."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'LISTENER'  # Uppercase
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Hello', '1234567890', None)

            # Assert - should still route correctly
            mock_reply_listener.assert_called_once()

    async def test_dispatch_with_mixed_case_mode(self):
        """Test that mode is case-insensitive (handles mixed case)."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_survey', new_callable=AsyncMock) as mock_reply_survey:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'SuRvEy'  # Mixed case
            mock_reply_survey.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Answer', '1234567890', None)

            # Assert - should still route correctly
            mock_reply_survey.assert_called_once()

    async def test_dispatch_no_current_event_id(self):
        """Test dispatching when user has no current_event_id."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks - no current_event_id
            mock_user_service.get_user.return_value = {
                'current_event_id': None,
                'events': []
            }
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Hello', '1234567890', None)

            # Assert - should route to listener without checking event
            mock_reply_listener.assert_called_once_with('Hello', '1234567890', None)

    async def test_dispatch_user_data_none(self):
        """Test dispatching when user data is None."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks - None user data
            mock_user_service.get_user.return_value = None
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Hello', '1234567890', None)

            # Assert - should route to listener
            mock_reply_listener.assert_called_once_with('Hello', '1234567890', None)

    async def test_dispatch_empty_current_event_id(self):
        """Test dispatching when current_event_id is empty string."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks - empty string event_id
            mock_user_service.get_user.return_value = {
                'current_event_id': '',
                'events': []
            }
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Hello', '1234567890', None)

            # Assert - should route to listener (empty string is falsy)
            mock_reply_listener.assert_called_once_with('Hello', '1234567890', None)

    async def test_dispatch_event_does_not_exist(self):
        """Test dispatching when event does not exist (raises 400)."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service:

            # Setup mocks - event doesn't exist
            mock_user_service.get_user.return_value = {
                'current_event_id': 'nonexistent123'
            }
            mock_event_service.event_exists.return_value = False

            # Execute & Assert - should raise HTTPException with 400
            with self.assertRaises(HTTPException) as context:
                await dispatch_message('Hello', '1234567890', None)

            self.assertEqual(context.exception.status_code, 400)
            self.assertEqual(context.exception.detail, "Unknown event ID")

    async def test_dispatch_unrecognized_mode(self):
        """Test dispatching with unrecognized mode (raises 500)."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service:

            # Setup mocks - unrecognized mode
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'unknown_mode'

            # Execute & Assert - should raise HTTPException with 500
            with self.assertRaises(HTTPException) as context:
                await dispatch_message('Hello', '1234567890', None)

            self.assertEqual(context.exception.status_code, 500)
            self.assertIn("Unrecognized mode 'unknown_mode'", context.exception.detail)

    async def test_dispatch_mode_none_defaults_to_listener(self):
        """Test that None mode defaults to 'listener'."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks - mode is None
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = None
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute
            result = await dispatch_message('Hello', '1234567890', None)

            # Assert - should default to listener mode
            mock_reply_listener.assert_called_once_with('Hello', '1234567890', None)

    async def test_phone_number_normalization_with_plus(self):
        """Test phone number normalization removes + sign."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            mock_user_service.get_user.return_value = None
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute with + in phone number
            await dispatch_message('Hello', '+1234567890', None)

            # Assert - phone should be normalized (no +)
            mock_user_service.get_user.assert_called_once_with('1234567890')

    async def test_phone_number_normalization_with_dashes(self):
        """Test phone number normalization removes dashes."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            mock_user_service.get_user.return_value = None
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute with dashes in phone number
            await dispatch_message('Hello', '123-456-7890', None)

            # Assert - phone should be normalized (no dashes)
            mock_user_service.get_user.assert_called_once_with('1234567890')

    async def test_phone_number_normalization_with_spaces(self):
        """Test phone number normalization removes spaces."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            mock_user_service.get_user.return_value = None
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute with spaces in phone number
            await dispatch_message('Hello', '123 456 7890', None)

            # Assert - phone should be normalized (no spaces)
            mock_user_service.get_user.assert_called_once_with('1234567890')

    async def test_phone_number_normalization_complex(self):
        """Test phone number normalization with mixed formatting."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            mock_user_service.get_user.return_value = None
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute with complex formatting
            await dispatch_message('Hello', '+1-234 567-8900', None)

            # Assert - phone should be normalized (no +, -, or spaces)
            mock_user_service.get_user.assert_called_once_with('12345678900')

    async def test_dispatch_with_media_url(self):
        """Test dispatching message with MediaUrl0 parameter."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_listener', new_callable=AsyncMock) as mock_reply_listener:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'listener'
            mock_reply_listener.return_value = Mock(status_code=200)

            # Execute with MediaUrl0
            media_url = 'https://example.com/image.jpg'
            result = await dispatch_message('Check this out', '1234567890', media_url)

            # Assert - MediaUrl0 should be passed through
            mock_reply_listener.assert_called_once_with('Check this out', '1234567890', media_url)

    async def test_dispatch_preserves_original_phone_format(self):
        """Test that original phone format is passed to handlers."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_survey', new_callable=AsyncMock) as mock_reply_survey:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'survey'
            mock_reply_survey.return_value = Mock(status_code=200)

            # Execute with formatted phone
            original_phone = '+1-234-567-8900'
            await dispatch_message('Answer', original_phone, None)

            # Assert - original format should be passed to handler
            mock_reply_survey.assert_called_once_with('Answer', original_phone, None)

    async def test_dispatch_all_parameters_passed_through(self):
        """Test that all parameters are correctly passed through to handlers."""
        with patch('app.handlers.dispatcher.UserTrackingService') as mock_user_service, \
             patch('app.handlers.dispatcher.EventService') as mock_event_service, \
             patch('app.handlers.dispatcher.reply_followup', new_callable=AsyncMock) as mock_reply_followup:

            # Setup mocks
            mock_user_service.get_user.return_value = {
                'current_event_id': 'test123'
            }
            mock_event_service.event_exists.return_value = True
            mock_event_service.get_event_mode.return_value = 'followup'
            mock_reply_followup.return_value = Mock(status_code=200)

            # Execute with all parameters
            body = 'Test message with details'
            from_number = '+1234567890'
            media_url = 'https://example.com/media.mp4'

            await dispatch_message(body, from_number, media_url)

            # Assert - all parameters passed correctly
            mock_reply_followup.assert_called_once_with(body, from_number, media_url)


if __name__ == '__main__':
    unittest.main()
