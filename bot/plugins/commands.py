import os
import logging
import random
import asyncio
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.ia_filterdb import Media, get_file_details, unpack_new_file_id
from database.users_chats_db import db
from info import (CHANNELS, ADMINS, AUTH_CHANNEL, LOG_CHANNEL, PICS,
                  BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, PROTECT_CONTENT,
                  SHORTLINK_URL, SHORTLINK_API, VERIFY_EXPIRE, VERIFY_TUTORIAL,
                  MOVIE_GROUP, VERIFY_DAILY_LIMIT, SUB_LINK)
from utils import (get_settings, get_size, is_subscribed, save_group_settings, temp,
                   clean_caption, get_shortlink, make_verify_token,
                   get_time_greeting, get_daily_verify_info, mark_verified,
                   is_premium, track_search, get_most_searched,
                   get_weekly_trending, _current_week_key, check_fsub)
from database.connections_mdb import active_connection
import re
import json
import base64
import time

logger = logging.getLogger(__name__)

BATCH_FILES = {}


async def _send_fsub_message(bot, user_id: int, unjoined: list, deep_link: str = ""):
    """Send a beautiful force-subscribe message listing all unjoined channels."""
    ch_list = "\n".join(
        f"{i}. 📢 <b>{ch['title']}</b>" for i, ch in enumerate(unjoined, 1)
    )
    text = script.FSUB_TXT.format(count=len(unjoined), channel_list=ch_list)
    btn = [[InlineKeyboardButton(f"📢 Join {ch['title']}", url=ch['invite_link'])]
           for ch in unjoined]
    retry_data = f"fsub_retry#{deep_link}" if deep_link else "fsub_retry#"
    btn.append([InlineKeyboardButton("✅ I've Joined — Try Again", callback_data=retry_data)])
    await bot.send_message(
        chat_id=user_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )


def _build_start_buttons(user_id: int) -> InlineKeyboardMarkup:
    """Build the start message buttons depending on shortlink config."""
    import info as _info
    sl_url = _info.SHORTLINK_URL
    sl_api = _info.SHORTLINK_API
    sub_link = _info.SUB_LINK
    movie_group = _info.MOVIE_GROUP

    if sl_url and sl_api:
        vinfo = get_daily_verify_info(user_id)
        rows = []
        if not vinfo['verified'] and not is_premium(user_id):
            verify_cb = f"do_verify_{user_id}"
            how_url = _info.VERIFY_TUTORIAL or "https://t.me/BackupChannel5211"
            rows.append([
                InlineKeyboardButton('• VERIFY •', callback_data=verify_cb),
                InlineKeyboardButton('• HOW TO VERIFY •', url=how_url),
            ])
            if sub_link:
                rows.append([InlineKeyboardButton('❗ BUY SUBSCRIPTION - NO NEED TO VERIFY ❗', url=sub_link)])
        else:
            rows.append([InlineKeyboardButton('✅ VERIFIED — GET FILES IN GROUPS', url=f'http://t.me/{temp.U_NAME}?startgroup=true')])
        rows.append([
            InlineKeyboardButton('Most Search 🔍', callback_data='most_search'),
            InlineKeyboardButton('Top Trending ⚡', callback_data='top_trending'),
        ])
        if movie_group:
            rows.append([InlineKeyboardButton('○ JOIN MOVIE GROUP ○', url=movie_group)])
        rows.append([
            InlineKeyboardButton('📢 Updates', url='https://t.me/BackupChannel5211'),
            InlineKeyboardButton('📢 Backup', url='https://t.me/backupchannek'),
        ])
        rows.append([
            InlineKeyboardButton('• PREMIUM •', callback_data='premium_info'),
            InlineKeyboardButton('• ABOUT •', callback_data='about'),
        ])
        return InlineKeyboardMarkup(rows)
    else:
        rows = [
            [InlineKeyboardButton('➕ Add Me To Your Group ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')],
            [
                InlineKeyboardButton('🔍 Inline Search', switch_inline_query_current_chat=''),
                InlineKeyboardButton('📢 Updates', url='https://t.me/BackupChannel5211'),
            ],
            [
                InlineKeyboardButton('📢 Backup', url='https://t.me/backupchannek'),
                InlineKeyboardButton('❓ Help', callback_data='help'),
            ],
            [InlineKeyboardButton('ℹ️ About', callback_data='about')],
        ]
        return InlineKeyboardMarkup(rows)


def _build_start_caption(user_id: int, name: str) -> str:
    """Build the start caption text."""
    import info as _info
    sl_url = _info.SHORTLINK_URL
    sl_api = _info.SHORTLINK_API
    greeting = get_time_greeting()
    if sl_url and sl_api:
        if is_premium(user_id):
            return script.START_TXT_VERIFIED.format(
                name=name, greeting=greeting,
                count='∞', limit='∞'
            )
        vinfo = get_daily_verify_info(user_id)
        if vinfo['verified']:
            return script.START_TXT_VERIFIED.format(
                name=name, greeting=greeting,
                count=vinfo['count'], limit=vinfo['limit']
            )
        else:
            return script.START_TXT_UNVERIFIED.format(
                name=name, greeting=greeting,
                count=vinfo['count'], limit=vinfo['limit']
            )
    else:
        return script.START_TXT_NO_SHORTLINK.format(
            name=name, greeting=greeting,
            uname=temp.U_NAME, bname=temp.B_NAME
        )


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        buttons = [
            [
                InlineKeyboardButton('📢 Updates', url='https://t.me/BackupChannel5211'),
                InlineKeyboardButton('📢 Backup', url='https://t.me/backupchannek'),
            ],
            [InlineKeyboardButton('❓ Help', url=f"https://t.me/{temp.U_NAME}?start=help")],
        ]
        await message.reply(
            f"👋 Hey {message.from_user.mention if message.from_user else message.chat.title}!\n\nI'm online and ready. Search a movie name in this group!",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            if LOG_CHANNEL:
                await client.send_message(
                    LOG_CHANNEL,
                    script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown")
                )
            await db.add_chat(message.chat.id, message.chat.title)
        return

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        if LOG_CHANNEL:
            await client.send_message(
                LOG_CHANNEL,
                script.LOG_TEXT_P.format(message.from_user.id, message.from_user.mention)
            )

    # ── No deep-link arg: show home screen ───────────────────────────────────
    if len(message.command) != 2:
        name = message.from_user.first_name
        caption = _build_start_caption(message.from_user.id, name)
        buttons = _build_start_buttons(message.from_user.id)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=caption,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML
        )
        return

    # ── Force-subscribe check ─────────────────────────────────────────────────
    unjoined = await check_fsub(client, message.from_user.id)
    if unjoined:
        deep = message.command[1] if len(message.command) == 2 else ""
        await _send_fsub_message(client, message.from_user.id, unjoined, deep)
        return

    if len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]:
        name = message.from_user.first_name
        caption = _build_start_caption(message.from_user.id, name)
        buttons = _build_start_buttons(message.from_user.id)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=caption,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML
        )
        return

    data = message.command[1]

    # ── Verify token (shortlink bypass) ───────────────────────────────────────
    if data.startswith("verify_"):
        token = data[7:]
        info = temp.VERIFY_TOKENS.get(token)
        if not info:
            return await message.reply("❌ This link has expired. Please search for the file again.")
        if time.time() > info['expires_at']:
            temp.VERIFY_TOKENS.pop(token, None)
            return await message.reply("⏰ Link expired. Please search for the file again.")
        if info['user_id'] != message.from_user.id:
            return await message.reply("❌ This link is not for you.")
        temp.VERIFY_TOKENS.pop(token, None)
        mark_verified(message.from_user.id)
        file_id = info.get('file_id')
        pre = info.get('pre', 'file')

        # Daily-verification token (no specific file attached)
        if not file_id or info.get('pre') == 'daily':
            vinfo = get_daily_verify_info(message.from_user.id)
            name = message.from_user.first_name
            caption = _build_start_caption(message.from_user.id, name)
            buttons = _build_start_buttons(message.from_user.id)
            await message.reply_photo(
                photo=random.choice(PICS),
                caption=f"✅ <b>Verification successful!</b>\n\n<b>#VERIFICATION:-</b> {vinfo['count']}/{vinfo['limit']} ✔️\n\n{caption}",
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML
            )
            return

        files_ = await get_file_details(file_id)
        if files_:
            files = files_[0]
            title = clean_caption(files.file_name)
            size = get_size(files.file_size)
            f_caption = clean_caption(files.caption)
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption='' if f_caption is None else f_caption
                    )
                except Exception:
                    pass
            if f_caption is None:
                f_caption = clean_caption(files.file_name)
        else:
            f_caption = ""
        await client.send_cached_media(
            chat_id=message.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if pre == 'filep' else False,
        )
        return

    # ── Referral link ─────────────────────────────────────────────────────────
    if data.startswith("ref_"):
        code = data[4:]
        from utils import process_refer
        referrer_id, milestone_hit = process_refer(message.from_user.id, code)
        if referrer_id and milestone_hit:
            # Auto-grant premium and notify referrer
            temp.PREMIUM_USERS.add(referrer_id)
            import info as _ref_info
            try:
                await client.send_message(
                    referrer_id,
                    f"🎉 <b>Congratulations!</b>\n\n"
                    f"You've hit <b>{_ref_info.REFER_PREMIUM_THRESHOLD} referrals</b>!\n"
                    f"<b>Premium access has been granted automatically.</b>\n\n"
                    f"You can now get files without any verification. 💎\n"
                    f"Keep inviting to earn Premium again next milestone!",
                    parse_mode="html"
                )
            except Exception:
                pass
        elif referrer_id:
            from utils import get_refer_stats
            stats = get_refer_stats(referrer_id)
            try:
                await client.send_message(
                    referrer_id,
                    f"✅ Someone joined via your referral link!\n"
                    f"👥 You've now invited <b>{stats['count']}</b> / {stats['threshold']} people.\n"
                    f"{'🔥 ' + str(stats['remaining']) + ' more to go for Premium!' if stats['remaining'] else ''}",
                    parse_mode="html"
                )
            except Exception:
                pass
        # Show normal start screen after referral recorded
        name = message.from_user.first_name
        caption = _build_start_caption(message.from_user.id, name)
        buttons = _build_start_buttons(message.from_user.id)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=caption,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML
        )
        return

    try:
        pre, file_id = data.split('_', 1)
    except Exception:
        file_id = data
        pre = ""

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("Please wait")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try:
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
            except Exception:
                await sts.edit("FAILED")
                if LOG_CHANNEL:
                    await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
                return
            os.remove(file)
            BATCH_FILES[file_id] = msgs
        for msg in msgs:
            title = msg.get("title")
            size = get_size(int(msg.get("size", 0)))
            f_caption = msg.get("caption", "")
            if BATCH_FILE_CAPTION:
                try:
                    f_caption = BATCH_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption='' if f_caption is None else f_caption
                    )
                except Exception as e:
                    logger.exception(e)
            if f_caption is None:
                f_caption = f"{title}"
            f_caption = clean_caption(f_caption)
            try:
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    protect_content=msg.get('protect', False),
                )
            except Exception as e:
                logger.warning(e, exc_info=True)
                continue
            await asyncio.sleep(1)
        await sts.delete()
        return

    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("Please wait")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except Exception:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if PROTECT_CONTENT else "batch"
        async for msg in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):
            if msg.media:
                media = getattr(msg, msg.media)
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption = BATCH_FILE_CAPTION.format(
                            file_name=getattr(media, 'file_name', ''),
                            file_size=getattr(media, 'file_size', ''),
                            file_caption=getattr(msg, 'caption', '')
                        )
                    except Exception as e:
                        logger.exception(e)
                        f_caption = getattr(msg, 'caption', '')
                else:
                    file_name = getattr(media, 'file_name', '')
                    f_caption = getattr(msg, 'caption', file_name)
                f_caption = clean_caption(f_caption)
                try:
                    await msg.copy(message.chat.id, caption=f_caption,
                                   protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await msg.copy(message.chat.id, caption=f_caption,
                                   protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            elif msg.empty:
                continue
            else:
                try:
                    await msg.copy(message.chat.id,
                                   protect_content=True if protect == "/pbatch" else False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await msg.copy(message.chat.id,
                                   protect_content=True if protect == "/pbatch" else False)
                except Exception as e:
                    logger.exception(e)
                    continue
            await asyncio.sleep(1)
        return await sts.delete()

    files_ = await get_file_details(file_id)
    if not files_:
        pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        try:
            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file_id,
                protect_content=True if pre == 'filep' else False,
            )
            filetype = msg.media
            file = getattr(msg, filetype)
            title = file.file_name
            size = get_size(file.file_size)
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption=''
                    )
                except Exception:
                    return
            await msg.edit_caption(f_caption)
            return
        except Exception:
            pass
        return await message.reply('No such file exist.')

    files = files_[0]
    title = files.file_name
    size = get_size(files.file_size)
    f_caption = files.caption
    if CUSTOM_FILE_CAPTION:
        try:
            f_caption = CUSTOM_FILE_CAPTION.format(
                file_name='' if title is None else title,
                file_size='' if size is None else size,
                file_caption='' if f_caption is None else f_caption
            )
        except Exception as e:
            logger.exception(e)
    if f_caption is None:
        f_caption = f"{files.file_name}"
    await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=True if pre == 'filep' else False,
    )


# ── PM text → redirect to movie group ─────────────────────────────────────────
@Client.on_message(filters.private & filters.text & filters.incoming & ~filters.command([
    'start', 'filter', 'filters', 'del', 'delall', 'id', 'info', 'imdb', 'search',
    'connect', 'disconnect', 'connections', 'settings', 'genlink', 'batch',
    'broadcast', 'grp_broadcast', 'ban', 'unban', 'channel', 'logs', 'delete',
    'stats', 'users', 'chats', 'leave', 'disable', 'shortlink', 'shortlink2',
    'shortlink3', 'tutorial', 'tutorial2', 'tutorial3', 'set_log', 'set_caption',
    'fsu', 'del_fsub', 'show_fsub', 'ginfo', 'shortlink_status', 'shortlink_stats', 'set_template',
    'premium', 'unpremium', 'set_sub_link', 'set_movie_group', 'set_daily_verify',
    'help', 'list_premium', 'trending', 'refer', 'refer_stats', 'set_refer_threshold',
]))
async def pm_text_redirect(client, message):
    import info as _info
    name = message.from_user.first_name
    movie_group = _info.MOVIE_GROUP
    btn = []
    if movie_group:
        btn.append([InlineKeyboardButton('🔍 MOVIE GROUP 🔍', url=movie_group)])
    btn.append([
        InlineKeyboardButton('🤖 Updates', url='https://t.me/BackupChannel5211'),
        InlineKeyboardButton('📢 Backup', url='https://t.me/backupchannek'),
    ])
    await message.reply(
        script.PM_REDIRECT.format(name=name),
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )


# ── do_verify callback (send shortlink for daily verification) ─────────────────
@Client.on_callback_query(filters.regex(r'^do_verify_'))
async def do_verify_callback(client, query):
    import info as _info
    user_id = query.from_user.id
    sl_url = _info.SHORTLINK_URL
    sl_api = _info.SHORTLINK_API
    if not sl_url or not sl_api:
        return await query.answer("Shortlink not configured by admin.", show_alert=True)
    if is_premium(user_id):
        return await query.answer("You are PREMIUM — no verification needed! ✅", show_alert=True)
    vinfo = get_daily_verify_info(user_id)
    if vinfo['verified']:
        return await query.answer("Already verified for today! ✅", show_alert=True)
    token = make_verify_token(user_id, f"daily_{user_id}")
    temp.VERIFY_TOKENS[token] = {
        'file_id': None,
        'pre': 'daily',
        'user_id': user_id,
        'expires_at': time.time() + _info.VERIFY_EXPIRE,
    }
    bot_link = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
    short = await get_shortlink(bot_link, sl_url, sl_api)
    how_url = _info.VERIFY_TUTORIAL or "https://t.me/BackupChannel5211"
    btn = [
        [InlineKeyboardButton("🚀 VERIFY NOW", url=short)],
        [InlineKeyboardButton("📖 How To Verify", url=how_url)],
    ]
    await query.answer()
    await query.message.reply(
        f"👇 <b>Click VERIFY NOW to complete your verification.</b>\n\n"
        f"<b>#VERIFICATION:-</b> {vinfo['count']}/{vinfo['limit']} ✔️\n\n"
        f"After clicking, come back here and send <code>/start</code> to check your status.",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )


# ── Most Search callback ───────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex('^most_search$'))
async def most_search_callback(client, query):
    top = get_most_searched(10)
    if not top:
        return await query.answer("No searches recorded yet!", show_alert=True)
    text = "<b>🔍 Most Searched Movies</b>\n\n"
    for i, (title, count) in enumerate(top, 1):
        text += f"{i}. <b>{title}</b> — <code>{count}</code> searches\n"
    btn = [[InlineKeyboardButton("🔙 Back", callback_data="start_home")]]
    await query.answer()
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except Exception:
        await query.message.reply(text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)


# ── Top Trending callback ──────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex('^top_trending$'))
async def top_trending_callback(client, query):
    await query.answer()
    top = get_weekly_trending(10)
    week = _current_week_key()
    btn = [[InlineKeyboardButton("🔙 Back", callback_data="start_home")]]
    if not top:
        text = (
            f"<b>⚡ Top Trending This Week</b> (<code>{week}</code>)\n\n"
            "<i>No searches recorded yet this week.\n"
            "Search movies in your group to see them here!</i>"
        )
    else:
        medals = ["🥇", "🥈", "🥉"]
        text = f"<b>⚡ Top Trending This Week</b> (<code>{week}</code>)\n\n"
        for i, (title, count) in enumerate(top, 1):
            prefix = medals[i - 1] if i <= 3 else f"{i}."
            bar = "▓" * min(count, 10)
            text += f"{prefix} <b>{title}</b>\n   {bar} <code>{count}</code> search{'es' if count != 1 else ''}\n"
        text += "\n<i>Updated in real-time as users search.</i>"
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except Exception:
        await query.message.reply(text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)


# ── /trending command ──────────────────────────────────────────────────────────
@Client.on_message(filters.command("trending") & filters.incoming)
async def trending_cmd(client, message):
    top = get_weekly_trending(10)
    week = _current_week_key()
    if not top:
        text = (
            f"<b>⚡ Top Trending This Week</b> (<code>{week}</code>)\n\n"
            "<i>No searches recorded yet this week.\n"
            "Search movies in your group to start tracking!</i>"
        )
    else:
        medals = ["🥇", "🥈", "🥉"]
        text = f"<b>⚡ Top Trending This Week</b> (<code>{week}</code>)\n\n"
        for i, (title, count) in enumerate(top, 1):
            prefix = medals[i - 1] if i <= 3 else f"{i}."
            bar = "▓" * min(count, 10)
            text += f"{prefix} <b>{title}</b>\n   {bar} <code>{count}</code> search{'es' if count != 1 else ''}\n"
        text += "\n<i>Updated in real-time as users search.</i>"
    await message.reply(text, parse_mode=enums.ParseMode.HTML)


# ── Premium info callback ──────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex('^premium_info$'))
async def premium_info_callback(client, query):
    import info as _info
    sub_link = _info.SUB_LINK
    user_id = query.from_user.id
    if is_premium(user_id):
        text = "⭐️ <b>You are a PREMIUM user!</b>\n\nYou get direct file access without any verification. Enjoy! 🎉"
        btn = [[InlineKeyboardButton("🔙 Back", callback_data="start_home")]]
    else:
        text = (
            "⭐️ <b>PREMIUM SUBSCRIPTION</b>\n\n"
            "✅ No daily verification needed\n"
            "✅ Get files instantly without clicking links\n"
            "✅ Unlimited file access\n"
            "✅ Priority support\n\n"
            "Contact the admin to purchase premium access."
        )
        btn = []
        if sub_link:
            btn.append([InlineKeyboardButton("💳 Buy Subscription", url=sub_link)])
        btn.append([InlineKeyboardButton("🔙 Back", callback_data="start_home")])
    await query.answer()
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except Exception:
        await query.message.reply(text, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)


# ── start_home callback (back button) ─────────────────────────────────────────
@Client.on_callback_query(filters.regex('^start_home$'))
async def start_home_callback(client, query):
    user_id = query.from_user.id
    name = query.from_user.first_name
    caption = _build_start_caption(user_id, name)
    buttons = _build_start_buttons(user_id)
    await query.answer()
    try:
        await query.message.edit_text(caption, reply_markup=buttons, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


# ── /help command + multi-page callbacks ──────────────────────────────────────

def _help_admin_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 GLOBAL FILTER", callback_data="help_filter"),
            InlineKeyboardButton("👥 USER & CHAT",   callback_data="help_user_chat"),
        ],
        [InlineKeyboardButton("💰 SHORTLINK & MONETIZATION", callback_data="help_shortlink")],
        [InlineKeyboardButton("🔙 BACK", callback_data="start_home")],
    ])

def _help_filter_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 BACK", callback_data="help_admin")],
    ])

def _help_user_chat_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 BACK", callback_data="help_admin")],
    ])

def _help_shortlink_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 BACK", callback_data="help_admin")],
    ])

def _help_user_buttons(uname):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 Updates", url="https://t.me/BackupChannel5211"),
            InlineKeyboardButton("📢 Backup", url="https://t.me/backupchannek"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_home")],
    ])


@Client.on_message(filters.command('help'))
async def help_cmd(bot, message):
    user_id = message.from_user.id
    if user_id in ADMINS:
        await message.reply(
            script.HELP_ADMIN_TXT,
            reply_markup=_help_admin_buttons(),
            parse_mode=enums.ParseMode.HTML
        )
    else:
        await message.reply(
            script.HELP_USER_TXT.format(uname=temp.U_NAME or "bot"),
            reply_markup=_help_user_buttons(temp.U_NAME),
            parse_mode=enums.ParseMode.HTML
        )


@Client.on_callback_query(filters.regex('^help$'))
async def help_callback(client, query):
    user_id = query.from_user.id
    await query.answer()
    if user_id in ADMINS:
        txt = script.HELP_ADMIN_TXT
        btn = _help_admin_buttons()
    else:
        txt = script.HELP_USER_TXT.format(uname=temp.U_NAME or "bot")
        btn = _help_user_buttons(temp.U_NAME)
    try:
        await query.message.edit_text(txt, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
    except Exception:
        await client.send_message(query.from_user.id, txt, reply_markup=btn, parse_mode=enums.ParseMode.HTML)


@Client.on_callback_query(filters.regex('^help_admin$'))
async def help_admin_callback(client, query):
    await query.answer()
    try:
        await query.message.edit_text(
            script.HELP_ADMIN_TXT,
            reply_markup=_help_admin_buttons(),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex('^help_filter$'))
async def help_filter_callback(client, query):
    await query.answer()
    try:
        await query.message.edit_text(
            script.HELP_FILTER_TXT,
            reply_markup=_help_filter_buttons(),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex('^help_user_chat$'))
async def help_user_chat_callback(client, query):
    await query.answer()
    try:
        await query.message.edit_text(
            script.HELP_USER_CHAT_TXT,
            reply_markup=_help_user_chat_buttons(),
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex('^help_shortlink$'))
async def help_shortlink_callback(client, query):
    await query.answer()
    try:
        await query.message.edit_text(
            script.HELP_SHORTLINK_TXT,
            reply_markup=_help_shortlink_buttons(),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex('^about$'))
async def about_callback(client, query):
    await query.answer()
    txt = script.ABOUT_TXT.format(
        bname=temp.B_NAME or "Miviesfather",
        uname=temp.U_NAME or "Miviesfather_bot"
    )
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="start_home")],
    ])
    try:
        await query.message.edit_text(txt, reply_markup=btn, parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


@Client.on_message(filters.command('channel') & filters.user(ADMINS))
async def channel_info(bot, message):
    if isinstance(CHANNELS, (int, str)):
        channels = [CHANNELS]
    elif isinstance(CHANNELS, list):
        channels = CHANNELS
    else:
        raise ValueError("Unexpected type of CHANNELS")

    text = '📑 **Indexed channels/groups**\n'
    for channel in channels:
        try:
            chat = await bot.get_chat(channel)
            if chat.username:
                text += '\n@' + chat.username
            else:
                text += '\n' + (chat.title or chat.first_name)
        except Exception:
            text += f'\n{channel} (unable to fetch)'

    text += f'\n\n**Total:** {len(channels)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        fname = 'Indexed channels.txt'
        with open(fname, 'w') as f:
            f.write(text)
        await message.reply_document(fname)
        os.remove(fname)


@Client.on_message(filters.command('logs') & filters.user(ADMINS))
async def log_file(bot, message):
    try:
        await message.reply_document('/tmp/TelegramBot.log')
    except Exception as e:
        await message.reply(str(e))


# ── /stats ─────────────────────────────────────────────────────────────────────

async def _build_stats_text(bot) -> str:
    import psutil, time as _time
    from database.ia_filterdb import Media

    # DATABASE
    try:
        total_files = await Media.count_documents()
    except Exception:
        total_files = 0
    try:
        total_users = await db.total_users_count()
    except Exception:
        total_users = 0
    try:
        total_groups = await db.total_chat_count()
    except Exception:
        total_groups = 0
    try:
        db_size_raw = await db.get_db_size()
        if db_size_raw >= 1024 ** 3:
            db_size = f"{db_size_raw / 1024 ** 3:.2f} GiB"
        elif db_size_raw >= 1024 ** 2:
            db_size = f"{db_size_raw / 1024 ** 2:.2f} MiB"
        elif db_size_raw >= 1024:
            db_size = f"{db_size_raw / 1024:.2f} KiB"
        else:
            db_size = f"{db_size_raw} B"
    except Exception:
        db_size = "N/A"

    # SERVER
    elapsed = int(_time.time() - temp.BOT_START_TIME)
    h, rem = divmod(elapsed, 3600)
    m, s = divmod(rem, 60)
    uptime = f"{h:02d}h {m:02d}m {s:02d}s"

    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    def _fmt(b):
        if b >= 1024 ** 3:
            return f"{b / 1024 ** 3:.2f} GiB"
        return f"{b / 1024 ** 2:.2f} MiB"

    owner = f"@{temp.U_NAME}" if temp.U_NAME else "Admin"

    text = (
        "<pre>┌─────────────────────────┐\n"
        "│        DATABASE         │\n"
        "└─────────────────────────┘</pre>\n"
        f"🎬 <b>Movies Indexed</b> : <code>{total_files}</code>\n"
        f"👤 <b>Total Users</b>    : <code>{total_users}</code>\n"
        f"👥 <b>Total Groups</b>   : <code>{total_groups}</code>\n"
        f"💾 <b>DB Size</b>        : <code>{db_size}</code>\n\n"
        "<pre>┌─────────────────────────┐\n"
        "│         SERVER          │\n"
        "└─────────────────────────┘</pre>\n"
        f"⏰ <b>Uptime</b>         : <code>{uptime}</code>\n"
        f"🔥 <b>CPU Usage</b>      : <code>{cpu}%</code>\n"
        f"💿 <b>RAM Usage</b>      : <code>{ram.percent}%</code>\n"
        f"💽 <b>Disk Used</b>      : <code>{_fmt(disk.used)}</code>\n"
        f"📁 <b>Disk Free</b>      : <code>{_fmt(disk.free)}</code>\n\n"
        f"👑 <b>Owner:</b> {owner}"
    )
    return text


def _stats_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="stats_refresh"),
            InlineKeyboardButton("✖ Close",   callback_data="stats_close"),
        ]
    ])


@Client.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats_cmd(bot, message):
    msg = await message.reply("Fetching stats..", quote=True)
    text = await _build_stats_text(bot)
    await msg.edit_text(text, reply_markup=_stats_buttons(), parse_mode=enums.ParseMode.HTML)


@Client.on_callback_query(filters.regex(r'^stats_refresh$'))
async def stats_refresh(bot, query):
    await query.answer("Refreshing...")
    text = await _build_stats_text(bot)
    try:
        await query.message.edit_text(text, reply_markup=_stats_buttons(), parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r'^stats_close$'))
async def stats_close(bot, query):
    await query.answer()
    await query.message.delete()


@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete(bot, message):
    reply = message.reply_to_message
    if reply and reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Reply to file with /delete which you want to delete', quote=True)
        return

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')
        return

    file_id, file_ref = unpack_new_file_id(media.file_id)

    result = await Media.collection.delete_one({'_id': file_id})
    if result.deleted_count:
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        result = await Media.collection.delete_many({
            'file_name': file_name,
            'file_size': media.file_size,
            'mime_type': media.mime_type
        })
        if result.deleted_count:
            await msg.edit('File is successfully deleted from database')
        else:
            result = await Media.collection.delete_many({
                'file_name': media.file_name,
                'file_size': media.file_size,
                'mime_type': media.mime_type
            })
            if result.deleted_count:
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')


@Client.on_message(filters.command('deleteall') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="YES", callback_data="autofilter_delete")],
            [InlineKeyboardButton(text="CANCEL", callback_data="close_data")],
        ]),
        quote=True,
    )


@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, message):
    await Media.collection.drop()
    await message.answer('Piracy Is Crime')
    await message.message.edit('Successfully Deleted All The Indexed Files.')


@Client.on_message(filters.command('settings'))
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except Exception:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and userid not in ADMINS
    ):
        return

    s = await get_settings(grp_id)
    if s is not None:
        buttons = [
            [
                InlineKeyboardButton('Filter Button', callback_data=f'setgs#button#{s["button"]}#{grp_id}'),
                InlineKeyboardButton('Single' if s["button"] else 'Double', callback_data=f'setgs#button#{s["button"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('Bot PM', callback_data=f'setgs#botpm#{s["botpm"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if s["botpm"] else '❌ No', callback_data=f'setgs#botpm#{s["botpm"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('File Secure', callback_data=f'setgs#file_secure#{s["file_secure"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if s["file_secure"] else '❌ No', callback_data=f'setgs#file_secure#{s["file_secure"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('IMDB', callback_data=f'setgs#imdb#{s["imdb"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if s["imdb"] else '❌ No', callback_data=f'setgs#imdb#{s["imdb"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('Spell Check', callback_data=f'setgs#spell_check#{s["spell_check"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if s["spell_check"] else '❌ No', callback_data=f'setgs#spell_check#{s["spell_check"]}#{grp_id}'),
            ],
            [
                InlineKeyboardButton('Welcome', callback_data=f'setgs#welcome#{s["welcome"]}#{grp_id}'),
                InlineKeyboardButton('✅ Yes' if s["welcome"] else '❌ No', callback_data=f'setgs#welcome#{s["welcome"]}#{grp_id}'),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_text(
            text=f"<b>Change Your Settings for {title} As Your Wish ⚙</b>",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=message.id
        )


@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Checking template")
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except Exception:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and userid not in ADMINS
    ):
        return

    if len(message.command) < 2:
        return await sts.edit("No Input!!")
    template = message.text.split(" ", 1)[1]
    await save_group_settings(grp_id, 'template', template)
    await sts.edit(f"Successfully changed template for {title} to\n\n{template}")
