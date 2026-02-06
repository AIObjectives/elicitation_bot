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

    # Validate required fields
    if not Body or not From:
        logger.error(f"Missing required fields - Body: {Body}, From: {From}")
        return {"error": "Missing required fields Body or From"}

    return await dispatch_message(Body, From, MediaUrl0)
# This endpoint will handle incoming messages and dispatch them to the appropriate handler based on the event ID and mode.