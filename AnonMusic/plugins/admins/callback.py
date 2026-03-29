# Copyright (c) 2026 Vibe-Bots
# Open-sourced under MIT terms.
# Included within AnonMusic framework.

import asyncio
from typing import Optional

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from AnonMusic import YouTube, app
from AnonMusic.core.call import Anony
from AnonMusic.misc import SUDOERS, db
from AnonMusic.utils.database import (
    get_active_chats, get_lang, get_upvote_count, is_active_chat,
    is_music_playing, is_nonadmin_chat, music_off, music_on, set_loop,
)
from AnonMusic.utils.decorators.language import languageCB
from AnonMusic.utils.formatters import seconds_to_min
from AnonMusic.utils.inline import close_markup, stream_markup, stream_markup_timer
from AnonMusic.utils.thumbnails import gen_thumb as get_thumb
from config import (
    BANNED_USERS, SOUNCLOUD_IMG_URL, STREAM_IMG_URL, SUPPORT_CHAT,
    TELEGRAM_AUDIO_URL, TELEGRAM_VIDEO_URL, adminlist, confirmer, votemode, autoclean,
)
from strings import get_string

checker = {}
upvoters = {}


async def quick_alert(query: CallbackQuery, text: str, alert: bool = False):
    try:
        await query.answer(text, show_alert=alert)
    except:
        pass


def is_admin_or_sudo(query: CallbackQuery, chat_id: int) -> bool:
    if query.from_user.id in SUDOERS:
        return True
    admins = adminlist.get(chat_id)
    return admins and query.from_user.id in admins


@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def admin_callback_handler(client, query: CallbackQuery, _):
    data = query.data.strip()
    _, rest = data.split(None, 1)
    command, chat_info = rest.split("|")
    
    if "_" in chat_info:
        chat_id = int(chat_info.split("_")[0])
        counter = chat_info.split("_")[1]
    else:
        chat_id = int(chat_info)
        counter = None
    
    if not await is_active_chat(chat_id):
        return await quick_alert(query, _["general_5"], True)
    
    if command == "UpVote":
        await handle_upvote(query, chat_id, counter, _)
        return
    
    if not await is_nonadmin_chat(query.message.chat.id):
        if not is_admin_or_sudo(query, query.message.chat.id):
            await quick_alert(query, _["admin_14"], True)
            return
    
    await handle_stream_control(query, chat_id, command, _, counter)


async def handle_upvote(query: CallbackQuery, chat_id: int, counter: str, _):
    votemode.setdefault(chat_id, {})
    upvoters.setdefault(chat_id, {})
    upvoters[chat_id].setdefault(query.message.id, [])
    votemode[chat_id].setdefault(query.message.id, 0)
    
    msg_id = query.message.id
    
    if query.from_user.id in upvoters[chat_id][msg_id]:
        upvoters[chat_id][msg_id].remove(query.from_user.id)
        votemode[chat_id][msg_id] -= 1
        await quick_alert(query, _["admin_39"], True)
    else:
        upvoters[chat_id][msg_id].append(query.from_user.id)
        votemode[chat_id][msg_id] += 1
        await quick_alert(query, _["admin_38"], True)
    
    upvote_limit = await get_upvote_count(chat_id)
    current_votes = votemode[chat_id][msg_id]
    
    if current_votes >= upvote_limit:
        await finalize_upvote(query, chat_id, counter, upvote_limit, _)
    else:
        button = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                text=f"👍 {current_votes}",
                callback_data=f"ADMIN UpVote|{chat_id}_{counter}"
            )
        ]])
        await query.edit_message_reply_markup(reply_markup=button)


async def finalize_upvote(query: CallbackQuery, chat_id: int, counter: str, upvote_limit: int, _):
    try:
        exists = confirmer[chat_id][query.message.id]
        current = db[chat_id][0]
        if current["vidid"] != exists["vidid"] or current["file"] != exists["file"]:
            return await query.edit_message_text(_["admin_35"])
    except:
        return await query.edit_message_text(_["admin_36"])
    
    await query.edit_message_text(_["admin_37"].format(upvote_limit))
    await handle_stream_control(query, chat_id, "Skip", _, counter)


async def handle_stream_control(query: CallbackQuery, chat_id: int, command: str, _, counter: str = None):
    mention = query.from_user.mention
    
    if command == "Pause":
        if not await is_music_playing(chat_id):
            return await quick_alert(query, _["admin_1"], True)
        await quick_alert(query, "")
        await music_off(chat_id)
        await Anony.pause_stream(chat_id)
        await query.message.reply_text(_["admin_2"].format(mention), reply_markup=close_markup(_))
    
    elif command == "Resume":
        if await is_music_playing(chat_id):
            return await quick_alert(query, _["admin_3"], True)
        await quick_alert(query, "")
        await music_on(chat_id)
        await Anony.resume_stream(chat_id)
        await query.message.reply_text(_["admin_4"].format(mention), reply_markup=close_markup(_))
    
    elif command in ["Stop", "End"]:
        await quick_alert(query, "")
        await Anony.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await query.message.reply_text(_["admin_5"].format(mention), reply_markup=close_markup(_))
        await query.message.delete()
    
    elif command in ["Skip", "Replay"]:
        await handle_skip_or_replay(query, chat_id, command, mention, _, counter)


async def handle_skip_or_replay(query: CallbackQuery, chat_id: int, command: str, mention: str, _, counter: str = None):
    check = db.get(chat_id)
    if not check:
        return
    
    txt = f"➻ stream {'skipped' if command == 'Skip' else 're-played'} by : {mention}"
    
    if command == "Skip":
        try:
            popped = check.pop(0)
            if popped:
                autoclean.discard(popped["file"])
            if not check:
                await query.edit_message_text(txt)
                await query.message.reply_text(_["admin_6"].format(mention, query.message.chat.title), reply_markup=close_markup(_))
                return await Anony.stop_stream(chat_id)
        except:
            await query.edit_message_text(txt)
            await query.message.reply_text(_["admin_6"].format(mention, query.message.chat.title), reply_markup=close_markup(_))
            return await Anony.stop_stream(chat_id)
    
    await quick_alert(query, "")
    await process_next_track(query, chat_id, check, txt, _)


async def process_next_track(query: CallbackQuery, chat_id: int, check: list, txt: str, _):
    track = check[0]
    track["played"] = 0
    
    if "old_dur" in track:
        track["dur"] = track["old_dur"]
        track["seconds"] = track["old_second"]
        track["speed_path"] = None
        track["speed"] = 1.0
    
    videoid = track["vidid"]
    title = track["title"].title()
    duration = track["dur"]
    user = track["by"]
    streamtype = track["streamtype"]
    is_video = str(streamtype) == "video"
    
    image = None
    if videoid not in ["telegram", "soundcloud"]:
        try:
            image = await YouTube.thumbnail(videoid, "live_" in track["file"])
        except:
            pass
    
    if "live_" in track["file"]:
        success, link = await YouTube.video(videoid, True)
        if not success:
            return await query.message.reply_text(_["admin_7"].format(title), reply_markup=close_markup(_))
        await Anony.skip_stream(chat_id, link, video=is_video, image=image)
    
    elif "vid_" in track["file"]:
        mystic = await query.message.reply_text(_["call_7"], disable_web_page_preview=True)
        file_path, _ = await YouTube.download(videoid, mystic, videoid=True, video=is_video)
        await mystic.delete()
        await Anony.skip_stream(chat_id, file_path, video=is_video, image=image)
    
    elif "index_" in track["file"]:
        await Anony.skip_stream(chat_id, videoid, video=is_video)
    
    else:
        await Anony.skip_stream(chat_id, track["file"], video=is_video, image=image)
    
    await send_now_playing(query, chat_id, track, is_video, user, title, duration, videoid, _)
    await query.edit_message_text(txt, reply_markup=close_markup(_))


async def send_now_playing(query: CallbackQuery, chat_id: int, track: dict, is_video: bool, user: str, title: str, duration: str, videoid: str, _):
    button = stream_markup(_, chat_id)
    
    if videoid == "telegram":
        photo = TELEGRAM_VIDEO_URL if is_video else TELEGRAM_AUDIO_URL
        caption = _["stream_1"].format(SUPPORT_CHAT, title[:23], duration, user)
    elif videoid == "soundcloud":
        photo = TELEGRAM_VIDEO_URL if is_video else SOUNCLOUD_IMG_URL
        caption = _["stream_1"].format(SUPPORT_CHAT, title[:23], duration, user)
    else:
        photo = await get_thumb(videoid)
        caption = _["stream_1"].format(
            f"https://t.me/{app.username}?start=info_{videoid}",
            title[:23], duration, user
        )
    
    run = await query.message.reply_photo(photo=photo, caption=caption, reply_markup=InlineKeyboardMarkup(button))
    db[chat_id][0]["mystic"] = run
    db[chat_id][0]["markup"] = "stream" if videoid not in ["telegram", "soundcloud"] else "tg"


async def markup_timer():
    while True:
        await asyncio.sleep(7)
        for chat_id in await get_active_chats():
            try:
                if not await is_music_playing(chat_id):
                    continue
                
                playing = db.get(chat_id)
                if not playing or playing[0]["seconds"] == 0:
                    continue
                
                mystic = playing[0].get("mystic")
                if not mystic or checker.get(chat_id, {}).get(mystic.id) is False:
                    continue
                
                lang = await get_lang(chat_id)
                _ = get_string(lang)
                
                buttons = stream_markup_timer(
                    _, chat_id,
                    seconds_to_min(playing[0]["played"]),
                    playing[0]["dur"],
                )
                await mystic.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            except:
                continue


asyncio.create_task(markup_timer())
