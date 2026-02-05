"""
Pytest configuration and fixtures for all tests.

This file sets up mock environment variables and common test fixtures
to prevent import errors during test collection.
"""

import os
import sys
import json
import pytest
from unittest.mock import Mock, MagicMock, patch

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Mock Firebase credentials JSON
mock_firebase_creds = json.dumps({
    "type": "service_account",
    "project_id": "test-project",
    "private_key_id": "test-key-id",
    "private_key": "-----BEGIN PRIVATE KEY-----\ntest_private_key\n-----END PRIVATE KEY-----\n",
    "client_email": "test@test-project.iam.gserviceaccount.com",
    "client_id": "123456789",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40test-project.iam.gserviceaccount.com"
})

# Set mock environment variables before any imports
os.environ.setdefault('TWILIO_ACCOUNT_SID', 'test_account_sid')
os.environ.setdefault('TWILIO_AUTH_TOKEN', 'test_auth_token')
os.environ.setdefault('TWILIO_NUMBER', '+1234567890')
os.environ.setdefault('OPENAI_API_KEY', 'test_openai_key')
os.environ.setdefault('ASSISTANT_ID', 'test_assistant_id')
os.environ.setdefault('FIREBASE_CREDENTIALS_JSON', mock_firebase_creds)

# Mock Firebase admin to prevent actual initialization
sys.modules['firebase_admin'] = MagicMock()
sys.modules['firebase_admin.credentials'] = MagicMock()
sys.modules['firebase_admin.firestore'] = MagicMock()


@pytest.fixture(autouse=True)
def mock_firebase():
    """Mock Firebase Admin SDK to avoid actual database connections."""
    with patch('firebase_admin.credentials') as mock_creds, \
         patch('firebase_admin.firestore') as mock_firestore, \
         patch('firebase_admin.initialize_app'):

        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.client.return_value = mock_db

        yield mock_db


@pytest.fixture(autouse=True)
def mock_twilio():
    """Mock Twilio client to avoid actual API calls."""
    with patch('app.services.twilio_service.twilio_client') as mock_client:
        mock_messages = MagicMock()
        mock_client.messages = mock_messages
        yield mock_client


@pytest.fixture(autouse=True)
def mock_openai():
    """Mock OpenAI client to avoid actual API calls."""
    with patch('openai.OpenAI') as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_user_data():
    """Provide sample user tracking data for tests."""
    return {
        'events': [],
        'current_event_id': None,
        'awaiting_event_id': False,
        'awaiting_event_change_confirmation': False,
        'last_inactivity_prompt': None,
        'awaiting_extra_questions': False,
        'current_extra_question_index': 0,
        'invalid_attempts': 0
    }


@pytest.fixture
def sample_event_info():
    """Provide sample event info for tests."""
    return {
        'mode': 'followup',
        'initial_message': 'Thank you for participating!',
        'welcome_message': 'Welcome to our event!',
        'completion_message': 'Thank you for completing the survey!',
        'extra_questions': {},
        'second_round_claims_source': {
            'enabled': False
        }
    }


@pytest.fixture
def sample_participant_data():
    """Provide sample participant data for tests."""
    return {
        'name': None,
        'interactions': [],
        'event_id': 'test_event',
        'questions_asked': {},
        'responses': {}
    }
