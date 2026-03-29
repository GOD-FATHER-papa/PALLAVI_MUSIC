# Copyright (c) 2026 Vibe-Bots
# Open-sourced under MIT terms.
# Included within AnonMusic framework.


from pyrogram import filters
from pyrogram.types import Message

from AnonMusic import app
from AnonMusic.core.call import Anony

welcome = 20
close = 30


@app.on_message(filters.video_chat_started, group=welcome)
@app.on_message(filters.video_chat_ended, group=close)
async def welcome(_, message: Message):
    await Anony.stop_stream_force(message.chat.id)
