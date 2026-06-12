import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import broadcast_messages, get_poster
from info import ADMINS

logger = logging.getLogger(__name__)


@Client.on_message(filters.command('broadcast') & filters.user(ADMINS))
async def broadcast(bot: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text(
            "📡 <b>Broadcast Usage</b>\n\n"
            "Reply to any message and use:\n"
            "• <code>/broadcast</code> — send that message to all users\n\n"
            "Or for a rich movie announcement:\n"
            "• <code>/announce Movie Name</code> — fetches IMDb poster + adds Search button",
            parse_mode=enums.ParseMode.HTML
        )

    sts = await message.reply_text("📡 Broadcasting...")
    b_msg = message.reply_to_message

    # If it's a photo reply with a caption, offer to add a Search button automatically
    caption_text = b_msg.caption or ""
    photo = b_msg.photo
    add_search_btn = photo and caption_text.strip()

    users = await db.get_all_users()
    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0

    async for user in users:
        uid = int(user['id'])
        try:
            if add_search_btn:
                btn = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        f"🔍 Search: {caption_text.strip()[:40]}",
                        switch_inline_query=caption_text.strip()[:64]
                    )
                ]])
                await bot.send_photo(
                    chat_id=uid,
                    photo=b_msg.photo.file_id,
                    caption=caption_text,
                    reply_markup=btn,
                    parse_mode=enums.ParseMode.HTML
                )
                pprint, result = True, "Success"
            else:
                pprint, result = await broadcast_messages(uid, b_msg)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            pprint, result = await broadcast_messages(uid, b_msg)
        except Exception:
            pprint, result = False, "Error"

        if pprint:
            success += 1
        elif result == "Blocked":
            blocked += 1
        elif result == "Deleted":
            deleted += 1
        elif result == "Error":
            failed += 1
        done += 1
        if done % 20 == 0:
            await sts.edit(
                f"📡 <b>Broadcast in progress:</b>\n\n"
                f"Total: <code>{done}</code>\n"
                f"✅ Success: <code>{success}</code>\n"
                f"🚫 Blocked: <code>{blocked}</code>\n"
                f"❌ Failed: <code>{failed}</code>",
                parse_mode=enums.ParseMode.HTML
            )
        await asyncio.sleep(0.05)

    await sts.edit(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"Total: <code>{done}</code>\n"
        f"✅ Success: <code>{success}</code>\n"
        f"🚫 Blocked: <code>{blocked}</code>\n"
        f"🗑 Deleted: <code>{deleted}</code>\n"
        f"❌ Failed: <code>{failed}</code>",
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command('announce') & filters.user(ADMINS))
async def announce_movie(bot: Client, message: Message):
    """Broadcast a movie announcement with IMDb poster + Search This Movie button."""
    parts = message.text.strip().split(None, 1)
    if len(parts) < 2:
        return await message.reply_text(
            "🎬 <b>Usage:</b> <code>/announce Movie Name</code>\n\n"
            "Bot fetches the IMDb poster and broadcasts to <b>all users</b> with a\n"
            "🔍 <b>Search This Movie</b> button.",
            parse_mode=enums.ParseMode.HTML
        )

    movie_query = parts[1].strip()
    status_msg = await message.reply_text(
        f"🔍 Fetching IMDb info for <b>{movie_query}</b>...",
        parse_mode=enums.ParseMode.HTML
    )

    poster_data = await get_poster(movie_query)

    if poster_data and isinstance(poster_data, dict):
        title = poster_data.get('title') or movie_query
        year = poster_data.get('year', '')
        genres = poster_data.get('genres', '')
        rating = poster_data.get('rating', 'N/A')
        plot = poster_data.get('plot', '') or ''
        poster_url = poster_data.get('poster', '')
        imdb_url = poster_data.get('url', '')

        caption = f"🎬 <b>{title}</b>"
        if year:
            caption += f" ({year})"
        caption += "\n\n"
        if genres:
            caption += f"🎭 <b>Genre:</b> {genres}\n"
        if rating and rating != 'None':
            caption += f"⭐ <b>Rating:</b> {rating}/10\n"
        if plot:
            short_plot = plot[:300] + ('...' if len(plot) > 300 else '')
            caption += f"\n📖 {short_plot}\n"
        caption += "\n🔍 <b>Search this movie in our group!</b>"
    else:
        title = movie_query
        poster_url = None
        imdb_url = None
        caption = (
            f"🎬 <b>{movie_query}</b>\n\n"
            f"🔍 <b>Search this movie in our group!</b>"
        )

    import info as _info
    btn_rows = [[
        InlineKeyboardButton(
            f"🔍 Search: {title[:40]}",
            switch_inline_query=title[:64]
        )
    ]]
    if _info.MOVIE_GROUP:
        btn_rows.append([
            InlineKeyboardButton("🎬 Go to Movie Group", url=_info.MOVIE_GROUP)
        ])
    if imdb_url:
        btn_rows.append([
            InlineKeyboardButton("🌐 IMDb Page", url=imdb_url)
        ])
    btn = InlineKeyboardMarkup(btn_rows)

    await status_msg.edit(
        f"📡 Broadcasting announcement for <b>{title}</b>...",
        parse_mode=enums.ParseMode.HTML
    )

    users = await db.get_all_users()
    done = 0
    success = 0
    blocked = 0
    deleted = 0
    failed = 0

    async for user in users:
        uid = int(user['id'])
        try:
            if poster_url:
                await bot.send_photo(
                    chat_id=uid,
                    photo=poster_url,
                    caption=caption,
                    reply_markup=btn,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=uid,
                    text=caption,
                    reply_markup=btn,
                    parse_mode=enums.ParseMode.HTML
                )
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                if poster_url:
                    await bot.send_photo(uid, photo=poster_url, caption=caption, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
                else:
                    await bot.send_message(uid, text=caption, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
                success += 1
            except Exception:
                failed += 1
        except UserIsBlocked:
            blocked += 1
        except InputUserDeactivated:
            await db.delete_user(uid)
            deleted += 1
        except Exception as ex:
            logger.warning(f"announce: uid={uid} error={ex}")
            failed += 1

        done += 1
        if done % 20 == 0:
            try:
                await status_msg.edit(
                    f"📡 <b>Announcing:</b> {title}\n\n"
                    f"Progress: <code>{done}</code>\n"
                    f"✅ Success: <code>{success}</code>\n"
                    f"🚫 Blocked: <code>{blocked}</code>\n"
                    f"❌ Failed: <code>{failed}</code>",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status_msg.edit(
        f"✅ <b>Announcement Complete!</b>\n\n"
        f"🎬 <b>{title}</b>\n\n"
        f"📊 Total: <code>{done}</code>\n"
        f"✅ Success: <code>{success}</code>\n"
        f"🚫 Blocked: <code>{blocked}</code>\n"
        f"🗑 Deleted: <code>{deleted}</code>\n"
        f"❌ Failed: <code>{failed}</code>",
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command('grp_broadcast') & filters.user(ADMINS))
async def broadcast_to_chats(bot: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast to groups.")

    sts = await message.reply_text("📡 Broadcasting to groups...")
    chats = await db.get_all_chats()
    b_msg = message.reply_to_message
    done = 0
    failed = 0
    success = 0

    async for chat in chats:
        try:
            await b_msg.copy(chat_id=int(chat['id']))
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await b_msg.copy(chat_id=int(chat['id']))
                success += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        done += 1
        if done % 10 == 0:
            await sts.edit(
                f"📡 <b>Group Broadcast in progress:</b>\n\n"
                f"Done: <code>{done}</code>\n"
                f"✅ Success: <code>{success}</code>\n"
                f"❌ Failed: <code>{failed}</code>",
                parse_mode=enums.ParseMode.HTML
            )
        await asyncio.sleep(0.5)

    await sts.edit(
        f"✅ <b>Group Broadcast Complete!</b>\n\n"
        f"Total: <code>{done}</code>\n"
        f"✅ Success: <code>{success}</code>\n"
        f"❌ Failed: <code>{failed}</code>",
        parse_mode=enums.ParseMode.HTML
    )
