import os
import sys
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from info import ADMINS

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def restart_bot(client: Client, message: Message):
    await message.reply_text(
        "🔄 <b>Restarting bot...</b>\n\nI will be back in a few seconds!",
        parse_mode="html"
    )
    logger.info(f"Restart triggered by admin {message.from_user.id}")
    await client.stop()
    os.execv(sys.executable, [sys.executable, "bot.py"])
