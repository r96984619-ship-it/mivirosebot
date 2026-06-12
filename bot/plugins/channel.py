import logging
from pyrogram import Client, filters, enums
from database.users_chats_db import db
from database.ia_filterdb import save_file
from utils import temp

logger = logging.getLogger(__name__)

@Client.on_message(
    filters.channel & (
        filters.document | filters.video | filters.audio
    ),
    group=-1
)
async def new_media(client, message):
    """Auto-index files posted in connected channels."""
    from info import CHANNELS
    if message.chat.id not in CHANNELS:
        return
    media = getattr(message, message.media.value, None)
    if not media:
        return
    media.file_type = message.media.value
    media.caption = message.caption
    saved, status = await save_file(media)
    if saved:
        logger.info(f"Auto-indexed: {getattr(media, 'file_name', media.file_id)}")
    elif status == 0:
        logger.debug(f"Duplicate skipped: {getattr(media, 'file_name', media.file_id)}")
