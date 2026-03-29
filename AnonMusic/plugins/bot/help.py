# Copyright (c) 2026 Vibe-Bots
# Open-sourced under MIT terms.
# Included within AnonMusic framework.

import asyncio
from functools import lru_cache
from typing import Dict, Union

from pyrogram import filters, types
from pyrogram.types import InlineKeyboardMarkup, Message
from cachetools import TTLCache

from AnonMusic import app
from AnonMusic.misc import SUDOERS
from AnonMusic.utils import help_pannel
from AnonMusic.utils.database import get_lang
from AnonMusic.utils.decorators.language import LanguageStart, languageCB
from AnonMusic.utils.inline.help import help_back_markup, private_help_panel
from config import BANNED_USERS, START_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers

help_cache = TTLCache(maxsize=100, ttl=300)

HELP_SECTIONS = {
    "hb1": helpers.HELP_1,
    "hb2": helpers.HELP_2,
    "hb3": helpers.HELP_3,
    "hb4": helpers.HELP_4,
    "hb5": helpers.HELP_5,
    "hb6": helpers.HELP_6,
    "hb7": helpers.HELP_7,
    "hb8": helpers.HELP_8,
    "hb9": helpers.HELP_9,
}

@app.on_message(filters.command(["help"]) & filters.private & ~BANNED_USERS)
async def helper_private(client: app, update: Message):
    try:
        await update.delete()
    except:
        pass
    
    language = await get_lang(update.chat.id)
    _ = get_string(language)
    keyboard = help_pannel(_)
    
    await update.reply_photo(
        photo=START_IMG_URL,
        has_spoiler=True,
        caption=_["help_1"].format(SUPPORT_CHAT),
        reply_markup=keyboard,
    )

@app.on_callback_query(filters.regex("settings_back_helper") & ~BANNED_USERS)
async def helper_back_callback(client: app, callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
    except:
        pass
    
    chat_id = callback_query.message.chat.id
    language = await get_lang(chat_id)
    _ = get_string(language)
    keyboard = help_pannel(_, True)
    
    await callback_query.edit_message_text(
        _["help_1"].format(SUPPORT_CHAT), 
        reply_markup=keyboard
    )

@app.on_message(filters.command(["help"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client: app, message: Message, _):
    keyboard = private_help_panel(_)
    await message.reply_text(
        _["help_2"], 
        reply_markup=InlineKeyboardMarkup(keyboard),
        quote=False
    )

@app.on_callback_query(filters.regex("help_callback") & ~BANNED_USERS)
@languageCB
async def helper_cb(client: app, callback_query: types.CallbackQuery, _):
    callback_data = callback_query.data.strip()
    cb = callback_data.split(None, 1)[1]
    keyboard = help_back_markup(_)
    
    cache_key = f"{cb}_{_}"
    if cache_key in help_cache:
        help_text = help_cache[cache_key]
        await callback_query.edit_message_text(help_text, reply_markup=keyboard)
        return
    
    if cb == "hb7" and callback_query.from_user.id not in SUDOERS:
        await callback_query.answer(
            "ᴛʜɪs ʙᴜᴛᴛᴏɴ ɪs ᴏɴʟʏ ғᴏʀ sᴜᴅᴏ ᴜsᴇʀs.", 
            show_alert=True
        )
        return
    
    help_text = HELP_SECTIONS.get(cb)
    if help_text:
        help_cache[cache_key] = help_text
        await callback_query.edit_message_text(help_text, reply_markup=keyboard)
    else:
        await callback_query.answer("Help section not found", show_alert=True)
