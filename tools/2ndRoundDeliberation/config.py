import os
import json
import logging
from decouple import config as _config
import firebase_admin
from firebase_admin import credentials, firestore
from twilio.rest import Client as TwilioClient
from openai import OpenAI as _OpenAI
import openai

# Environment variables
OPENAI_API_KEY      = _config('OPENAI_API_KEY')
TWILIO_ACCOUNT_SID  = _config('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN   = _config('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER       = _config('TWILIO_NUMBER')
ASSISTANT_ID        = _config('ASSISTANT_ID')
FIREBASE_CREDS_JSON = _config('FIREBASE_CREDENTIALS_JSON')

# Firebase setup
cred = credentials.Certificate(json.loads(FIREBASE_CREDS_JSON))
firebase_admin.initialize_app(cred)
db = firestore.client()

# Logging
logger = logging.getLogger("whatsapp_bot")
logging.basicConfig(level=logging.INFO)

# OpenAI client
openai.api_key = OPENAI_API_KEY
OpenAI = _OpenAI
client = OpenAI()
assistant_id = ASSISTANT_ID

# Twilio client
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
twilio_number     = TWILIO_NUMBER
twilio_account_sid = TWILIO_ACCOUNT_SID
twilio_auth_token  = TWILIO_AUTH_TOKEN


