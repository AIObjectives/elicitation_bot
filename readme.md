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


