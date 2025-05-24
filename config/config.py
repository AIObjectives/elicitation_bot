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




# import firebase_admin
# from firebase_admin import credentials, firestore
# from fastapi import FastAPI, Form, Response
# from openai import OpenAI
# from decouple import config
# import logging
# import json
# from twilio.rest import Client as TwilioClient


# import firebase_admin
# from firebase_admin import credentials, firestore
# from fastapi import FastAPI, Form, Response
# from openai import OpenAI
# from decouple import config
# import logging
# from twilio.rest import Client as TwilioClient
# import json
# import os

# #from agent_functions import generate_bot_instructions, send_message, extract_text_from_messages, generate_initial_message1, extract_name_with_llm, extract_event_id_with_llm, event_id_valid, create_welcome_message


# # firebase_admin.initialize_app(cred)


# firebase_credentials = json.loads(os.environ.get('FIREBASE_CREDS_JSON'))
# cred = credentials.Certificate(firebase_credentials)
# firebase_admin.initialize_app(cred)
# db = firestore.client()

# # # FastAPI app initialization
# # app = FastAPI()

# #===
# # cred = credentials.Certificate('/Users/emreturan/Desktop/firebase/aoiwhatsappbot-firebase-adminsdk-rki5n-9526831994.json')
# # firebase_admin.initialize_app(cred)
# # db = firestore.client()

# # FastAPI app initialization
# app = FastAPI()

# # OpenAI Configuration
# OpenAI.api_key = config("OPENAI_API_KEY")
# client = OpenAI(api_key=OpenAI.api_key)



# # Twilio Configuration
# twilio_account_sid = config("TWILIO_ACCOUNT_SID")
# twilio_auth_token = config("TWILIO_AUTH_TOKEN")
# twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)
# twilio_number = config('TWILIO_NUMBER')



# #assistant_id = "asst_Hd2y8q4VdTz9j07zA8m3vW85" ## AOI for AI conference/ gpt-4o shoudl be much cheaper!

# assistant_id = config('ASSISTANT_ID')

# # # Twilio Configuration
# # twilio_account_sid = config("TWILIO_ACCOUNT_SID")
# # twilio_auth_token = config("TWILIO_AUTH_TOKEN")
# # twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)
# # twilio_number = config('TWILIO_NUMBER')

# # Setup logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)



# from fastapi import HTTPException, Response, Form, UploadFile, File
# from uuid import uuid4
# import os

# import requests
# import io
# from pydub import AudioSegment

# from requests.auth import HTTPBasicAuth

# from openai import OpenAI


# import openai
# import re

# # Configuration
# openai_api_key = config('OPENAI_API_KEY')
# openai_engine = 'gpt-4o'
