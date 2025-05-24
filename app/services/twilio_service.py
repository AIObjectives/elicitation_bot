# # app/services/twilio_service.py
# import io
# import requests
# from requests.auth import HTTPBasicAuth
# from config.config import twilio_client, TWILIO_NUMBER, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, logger

# def send_message(to_number, body_text):
#     if not to_number.startswith('whatsapp:'):
#         to_number = f'whatsapp:{to_number}'
#     try:
#         message = twilio_client.messages.create(
#             body=body_text,
#             from_=f'whatsapp:{TWILIO_NUMBER}',
#             to=to_number
#         )
#         logger.info(f"Message sent to {to_number}: {body_text}")
#     except Exception as e:
#         logger.error(f"Error sending message to {to_number}: {e}")

# def transcribe_media(media_url):
#     try:
#         response = requests.get(media_url, auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
#         content_type = response.headers.get('Content-Type')
#         if 'audio' in content_type:
#             audio_stream = io.BytesIO(response.content)
#             audio_stream.name = 'file.ogg'
#             # Here you would call Twilio's transcription service (or another transcription API)
#             transcription = "Transcribed audio text"  # Replace with actual transcription call
#             return content_type, transcription
#         else:
#             return content_type, None
#     except Exception as e:
#         logger.error(f"Error transcribing media: {e}")
#         return None, None








from config.config import twilio_client, twilio_number, logger

# def send_message(to_number: str, body: str):
#     twilio_client.messages.create(
#         body=body,
#         from_=twilio_number,
#         to=to_number
#     )




def send_message(to_number, body):
    """Send a WhatsApp message via Twilio"""
    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'

    try:
        message = twilio_client.messages.create(
            body=body,
            from_=f'whatsapp:{twilio_number}',
            to=to_number
        )
        logger.info(f"Message sent to {to_number}: {message.body}")
    except Exception as e:
        logger.error(f"Error sending message to {to_number}: {e}")
