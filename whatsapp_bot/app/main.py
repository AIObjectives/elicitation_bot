from fastapi import FastAPI, Form, Request
from app.handlers.dispatcher import dispatch_message
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

@app.post("/message")
async def message_endpoint(
    request: Request,
    Body: str = Form(None),
    From: str = Form(None),
    MediaUrl0: str = Form(None)
):
    # Log the raw request for debugging
    form_data = await request.form()
    logger.info(f"Received form data: {dict(form_data)}")
    logger.info(f"Body={Body}, From={From}, MediaUrl0={MediaUrl0}")

    # Validate required fields - Body can be empty for audio messages
    if From is None:
        logger.error(f"Missing required field From: {From}")
        return {"error": "Missing required field From"}

    # Body can be empty string for audio/media messages, so only check if it's None
    if Body is None and MediaUrl0 is None:
        logger.error(f"Both Body and MediaUrl0 are missing")
        return {"error": "Either Body or MediaUrl0 must be provided"}

    return await dispatch_message(Body or "", From, MediaUrl0)
# This endpoint will handle incoming messages and dispatch them to the appropriate handler based on the event ID and mode.