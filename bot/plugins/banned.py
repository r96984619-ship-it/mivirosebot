from pyrogram import Client, filters
from database.users_chats_db import db
from utils import temp

async def banned_usr_check(flt, client, message):
    if message.from_user:
        user = message.from_user
        try:
            if user.id in temp.BANNED_USERS:
                return True
        except Exception:
            pass
    return False

async def banned_chat_check(flt, client, message):
    if message.chat:
        try:
            if message.chat.id in temp.BANNED_CHATS:
                return True
        except Exception:
            pass
    return False

banned_users = filters.create(banned_usr_check)
banned_chats = filters.create(banned_chat_check)

@Client.on_message(banned_users | banned_chats)
async def handle_banned(client, message):
    pass
