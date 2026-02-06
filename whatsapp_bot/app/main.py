from fastapi import FastAPI, Form
from app.handlers.dispatcher import dispatch_message

app = FastAPI()

@app.post("/message")
async def message_endpoint(
    Body: str = Form(...),
    From: str = Form(...),
    MediaUrl0: str = Form(default=None)
):
    return await dispatch_message(Body, From, MediaUrl0)
# This endpoint will handle incoming messages and dispatch them to the appropriate handler based on the event ID and mode.