whatsapp_bot/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI initialization
│   ├── routes.py             # API endpoint definitions
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── message_handler.py  # Core message processing logic (steps 1–10)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── firestore_service.py  # Firestore (database) interactions
│   │   ├── twilio_service.py     # Twilio integration (sending messages, transcription)
│   │   └── openai_service.py       # OpenAI API calls and LLM extractions
│   └── utils/
│       ├── __init__.py
│       ├── validators.py         # e.g. is_valid_name()
│       └── helpers.py            # Helper functions (duplicate removal, inactivity checks, etc.)
│
├── config/
│   ├── __init__.py
│   └── config.py                # Configuration settings (API keys, credentials, etc.)
│
├── tests/
│   ├── __init__.py
│   └── test_message_handler.py  # (Basic test for your endpoint - not fully verified end-to-end)
│
├── Procfile                     # For Heroku deployment
├── requirements.txt             # Python dependencies
└── README.md

# WhatsApp Bot

This project is an open-source WhatsApp bot deployed on Heroku. It integrates with Twilio for messaging, Firestore for data persistence, and OpenAI for LLM-based processing.

## Folder Structure

- **app/**: Application code  
  - **main.py**: FastAPI entrypoint  
  - **routes.py**: API endpoints  
  - **handlers/**: Business logic for processing messages  
  - **services/**: Integrations with Firestore, Twilio, and OpenAI  
  - **utils/**: Helper and validator functions

- **config/**: Configuration settings (API keys, credentials, etc.)

- **tests/**: Test cases

- **Procfile**: For Heroku deployment

- **requirements.txt**: Python dependencies


