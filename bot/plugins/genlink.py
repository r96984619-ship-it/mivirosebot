import re
import base64
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
from info import ADMINS, LOG_CHANNEL, FILE_STORE_CHANNEL, PROTECT_CONTENT, PUBLIC_FILE_STORE

logger = logging.getLogger(__name__)

@Client.on_message(filters.command('batch') & filters.user(ADMINS))
async def gen_batch(client, message):
    if not FILE_STORE_CHANNEL:
        return await message.reply_text("No FILE_STORE_CHANNEL configured.")

    if len(message.command) < 3:
        return await message.reply_text(
            "Usage: <code>/batch channel_id first_msg_id last_msg_id</code>",
        )

    try:
        channel_id = int(message.command[1])
        first = int(message.command[2])
        last = int(message.command[3]) if len(message.command) > 3 else first
    except Exception:
        return await message.reply_text("Invalid arguments. Provide integer IDs.")

    if channel_id not in FILE_STORE_CHANNEL:
        return await message.reply_text("Provided channel is not in FILE_STORE_CHANNEL list.")

    if first > last:
        first, last = last, first

    sts = await message.reply_text("Creating batch link...")

    # Encode as DSTORE link
    protect = "/pbatch" if PROTECT_CONTENT else "batch"
    string = f"{first}_{last}_{channel_id}_{protect}"
    b64 = base64.urlsafe_b64encode(string.encode("ascii")).decode().strip("=")
    link = f"https://t.me/{(await client.get_me()).username}?start=DSTORE-{b64}"
    await sts.edit_text(
        f"<b>Batch Link Generated!</b>\n\nLink: {link}",
        disable_web_page_preview=True
    )


@Client.on_message(filters.command('genlink') & filters.user(ADMINS))
async def gen_link(client, message):
    """Generate a start link for a file stored in a FILE_STORE_CHANNEL."""
    if not FILE_STORE_CHANNEL:
        return await message.reply_text("No FILE_STORE_CHANNEL configured.")

    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: Reply to a file or provide channel & message ID:\n"
            "<code>/genlink channel_id message_id</code>",
        )

    if message.reply_to_message and message.reply_to_message.media:
        msg = message.reply_to_message
    elif len(message.command) == 3:
        try:
            ch = int(message.command[1])
            mid = int(message.command[2])
            msg = await client.get_messages(ch, mid)
        except Exception as e:
            return await message.reply_text(f"Error: {e}")
    else:
        return await message.reply_text("Reply to a file with /genlink")

    if not msg or not msg.media:
        return await message.reply_text("That message has no media.")

    media = getattr(msg, msg.media.value, None)
    if not media:
        return await message.reply_text("Unsupported media type.")

    protect = "filep" if PROTECT_CONTENT else "file"
    file_id = media.file_id
    b64 = base64.urlsafe_b64encode(f"{protect}_{file_id}".encode("ascii")).decode().strip("=")
    link = f"https://t.me/{(await client.get_me()).username}?start={b64}"
    await message.reply_text(
        f"<b>Link Generated!</b>\n\nFile: <code>{getattr(media, 'file_name', file_id)}</code>\nLink: {link}",
        disable_web_page_preview=True
    )
