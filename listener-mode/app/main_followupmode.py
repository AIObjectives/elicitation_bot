from fastapi import FastAPI, Form
from app.handlers.followup_message_handler import reply_followup

app = FastAPI()

@app.post("/message/")
async def message_endpoint(
    Body: str = Form(...),
    From: str = Form(...),
    MediaUrl0: str = Form(default=None)
):
    return await reply_followup(Body, From, MediaUrl0)
