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
