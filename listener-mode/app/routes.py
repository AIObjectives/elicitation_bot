from fastapi import APIRouter, Form
from app.handlers.message_handler import reply

router = APIRouter()

@router.post("/message/")
async def message_endpoint(Body: str = Form(...), From: str = Form(...), MediaUrl0: str = Form(default=None)):
    return await reply(Body, From, MediaUrl0)
