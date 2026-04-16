import json
from decouple import config as _config

FIREBASE_CREDS_JSON = _config('FIREBASE_CREDENTIALS_JSON')
FIREBASE_CREDENTIALS = json.loads(FIREBASE_CREDS_JSON)

GCS_BUCKET_NAME = _config('GCS_BUCKET_NAME')
EMAIL_SENDER = _config('EMAIL_SENDER', default='info@talktothecity.org')
GMAIL_APP_PASSWORD = _config('GMAIL_APP_PASSWORD')
