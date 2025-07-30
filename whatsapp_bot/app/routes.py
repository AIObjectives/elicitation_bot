# from fastapi import APIRouter, Form
# from app.handlers.message_handler import reply

# router = APIRouter()

# @router.post("/message/")
# async def message_endpoint(Body: str = Form(...), From: str = Form(...), MediaUrl0: str = Form(default=None)):
#     return await reply(Body, From, MediaUrl0)


# This file is currently unused.
# Keep it for future scalability if multiple endpoints or route groups are added.
# To activate:
# 1. Define routes here using APIRouter()
# 2. Import and include with `app.include_router(router)` in main.py


from fastapi import APIRouter, Form
from app.handlers.dispatcher import dispatch_message

router = APIRouter()

@router.post("/message/")
async def message_endpoint(Body: str = Form(...), From: str = Form(...), MediaUrl0: str = Form(default=None)):
    return await dispatch_message(Body, From, MediaUrl0)
