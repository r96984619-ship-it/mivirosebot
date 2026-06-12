import time
import logging
from datetime import timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
from info import ADMINS, DATABASE_URI
from database.ia_filterdb import Media
from database.users_chats_db import db
from utils import get_most_searched

logger = logging.getLogger(__name__)

_BOT_START_TIME = time.time()


def _fmt_uptime(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    days = td.days
    hours, rem = divmod(td.seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


@Client.on_message(filters.command("status") & filters.user(ADMINS))
async def bot_status(client: Client, message: Message):
    msg = await message.reply("⏳ Fetching stats...")

    total_files = 0
    total_users = 0
    total_chats = 0
    mongo_status = "✅ Connected"

    try:
        total_files = await Media.count_documents({})
    except Exception as e:
        mongo_status = f"❌ Error: {e}"

    try:
        total_users = await db.total_users_count()
    except Exception:
        pass

    try:
        total_chats = await db.total_chat_count()
    except Exception:
        pass

    if not DATABASE_URI:
        mongo_status = "⚠️ No DATABASE_URI set (in-memory)"

    uptime = _fmt_uptime(time.time() - _BOT_START_TIME)

    top_searches = get_most_searched(top_n=5)
    if top_searches:
        search_lines = "\n".join(
            f"  {i}. {title} ({count}x)"
            for i, (title, count) in enumerate(top_searches, 1)
        )
    else:
        search_lines = "  No searches recorded yet"

    text = (
        f"<b>🤖 Bot Status</b>\n"
        f"{'─' * 30}\n\n"
        f"<b>⏱ Uptime:</b> <code>{uptime}</code>\n"
        f"<b>🗄 MongoDB:</b> {mongo_status}\n\n"
        f"<b>📊 Database Stats</b>\n"
        f"  🎬 Indexed Files: <code>{total_files:,}</code>\n"
        f"  👥 Total Users:   <code>{total_users:,}</code>\n"
        f"  💬 Total Groups:  <code>{total_chats:,}</code>\n\n"
        f"<b>🔍 Top Searches (this session)</b>\n"
        f"{search_lines}"
    )

    await msg.edit(text, parse_mode="html")
