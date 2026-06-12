import asyncio
import re
import ast
import math
import logging
from pyrogram.errors.exceptions.bad_request_400 import (
    MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
)
from Script import script
from database.connections_mdb import (
    active_connection, all_connections, delete_connection,
    if_active, make_active, make_inactive
)
from info import (ADMINS, AUTH_CHANNEL, AUTH_USERS, CUSTOM_FILE_CAPTION,
                  AUTH_GROUPS, P_TTI_SHOW_OFF, IMDB, SINGLE_BUTTON,
                  SPELL_CHECK_REPLY, IMDB_TEMPLATE, SHORTLINK_URL, SHORTLINK_API,
                  VERIFY_EXPIRE, VERIFY_TUTORIAL)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import (get_size, is_subscribed, get_poster, search_gagala, temp,
                   get_settings, save_group_settings, clean_caption,
                   get_shortlink, make_verify_token, get_daily_verify_info,
                   is_premium, track_search, track_weekly_search,
                   get_most_searched, get_time_greeting, check_fsub)
import time
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.filters_mdb import del_all, find_filter, get_filters

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}


@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    k = await manual_filters(client, message)
    if k == False:
        await auto_filter(client, message)


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer("oKda", show_alert=True)
    try:
        offset = int(offset)
    except Exception:
        offset = 0
    search = BUTTONS.get(key)
    if not search:
        await query.answer(
            "You are using one of my old messages, please send the request again.",
            show_alert=True
        )
        return

    files, n_offset, total = await get_search_results(search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except Exception:
        n_offset = 0

    if not files:
        return

    settings = await get_settings(query.message.chat.id)
    if settings['button']:
        btn = [
            [InlineKeyboardButton(
                text=f"[{get_size(file.file_size)}] {file.file_name}",
                callback_data=f'files#{file.file_id}'
            )]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(text=f"{file.file_name}", callback_data=f'files#{file.file_id}'),
                InlineKeyboardButton(text=f"{get_size(file.file_size)}", callback_data=f'files_#{file.file_id}'),
            ]
            for file in files
        ]

    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10

    if n_offset == 0:
        btn.append([
            InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
            InlineKeyboardButton(
                f"📃 Pages {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}",
                callback_data="pages"
            )
        ])
    elif off_set is None:
        btn.append([
            InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
            InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
        ])
    else:
        btn.append([
            InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
            InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
            InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
        ])

    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()


@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer("okDa", show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer(
            "You are clicking on an old button which is expired.",
            show_alert=True
        )
    movie = movies[int(movie_)]
    await query.answer('Checking for Movie in database...')
    k = await manual_filters(bot, query.message, text=movie)
    if k == False:
        files, offset, total_results = await get_search_results(movie, offset=0, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            k = await query.message.edit('This Movie Not Found In DataBase')
            await asyncio.sleep(10)
            await k.delete()


@Client.on_callback_query(filters.regex(r'^setgs#'))
async def settings_callback(client, query):
    data = query.data.split('#')
    # setgs#key#current_value#grp_id
    _, key, curr_val, grp_id = data
    grp_id = int(grp_id)
    userid = query.from_user.id

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and userid not in ADMINS
    ):
        return await query.answer("You don't have permission to change settings.", show_alert=True)

    # Toggle the value
    current = await get_settings(grp_id)
    if curr_val == 'True':
        new_val = False
    elif curr_val == 'False':
        new_val = True
    else:
        new_val = not bool(curr_val)

    await save_group_settings(grp_id, key, new_val)
    await query.answer(f"Setting '{key}' updated!")

    # Rebuild the settings keyboard
    s = await get_settings(grp_id)
    try:
        chat = await client.get_chat(grp_id)
        title = chat.title
    except Exception:
        title = str(grp_id)

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
    try:
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        await query.message.delete()

    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except Exception:
                    await query.message.edit_text("Make sure I'm present in your group!!", quote=True)
                    return await query.answer('Piracy Is Crime')
            else:
                await query.message.edit_text(
                    "I'm not connected to any groups!\nCheck /connections or connect to any groups",
                    quote=True
                )
                return await query.answer('Piracy Is Crime')
        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title
        else:
            return await query.answer('Piracy Is Crime')

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.OWNER) or (userid in ADMINS):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("You need to be Group Owner or an Auth User to do that!", show_alert=True)

    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type
        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()
        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.OWNER) or (userid in ADMINS):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except Exception:
                    pass
            else:
                await query.answer("That's not for you!!", show_alert=True)

    elif "groupcb" in query.data:
        await query.answer()
        group_id = query.data.split(":")[1]
        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
                InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")
            ],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])
        await query.message.edit_text(
            f"Group Name : **{title}**\nGroup ID : `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )

    elif "connectcb" in query.data:
        await query.answer()
        group_id = query.data.split(":")[1]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        mkact = await make_active(str(user_id), str(group_id))
        if mkact:
            await query.message.edit_text(f"Connected to **{title}**", parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await query.message.edit_text('Some error occurred!!', parse_mode=enums.ParseMode.MARKDOWN)

    elif "disconnect" in query.data and "connectcb" not in query.data:
        await query.answer()
        group_id = query.data.split(":")[1]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id
        mkinact = await make_inactive(str(user_id))
        if mkinact:
            await query.message.edit_text(f"Disconnected from **{title}**", parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await query.message.edit_text("Some error occurred!!", parse_mode=enums.ParseMode.MARKDOWN)

    elif "deletecb" in query.data:
        await query.answer()
        user_id = query.from_user.id
        group_id = query.data.split(":")[1]
        delcon = await delete_connection(str(user_id), str(group_id))
        if delcon:
            await query.message.edit_text("Successfully deleted connection")
        else:
            await query.message.edit_text("Some error occurred!!", parse_mode=enums.ParseMode.MARKDOWN)

    elif query.data == "backcb":
        await query.answer()
        userid = query.from_user.id
        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text("There are no active connections!! Connect to some groups first.")
            return
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append([InlineKeyboardButton(
                    text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                )])
            except Exception:
                pass
        if buttons:
            await query.message.edit_text(
                "Your connected group details ;\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)

    elif query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
        files = files_[0]
        title = clean_caption(files.file_name)
        size = get_size(files.file_size)
        f_caption = clean_caption(files.caption)
        settings = await get_settings(query.message.chat.id)
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
            f_caption = clean_caption(files.file_name)
        try:
            # ── Force-subscribe gate ──────────────────────────────────────
            unjoined = await check_fsub(client, query.from_user.id)
            if unjoined:
                await query.answer("⚠️ Please join our channels first!", show_alert=True)
                ch_list = "\n".join(
                    f"{i}. 📢 <b>{ch['title']}</b>" for i, ch in enumerate(unjoined, 1)
                )
                from Script import script as _script
                text = _script.FSUB_TXT.format(count=len(unjoined), channel_list=ch_list)
                btn = [[InlineKeyboardButton(f"📢 Join {ch['title']}", url=ch['invite_link'])]
                       for ch in unjoined]
                btn.append([InlineKeyboardButton(
                    "✅ I've Joined — Try Again",
                    callback_data=f"fsub_retry#{ident}_{file_id}"
                )])
                await client.send_message(
                    chat_id=query.from_user.id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.HTML
                )
                return
            elif settings['botpm']:
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                return

            # ── Shortlink / Verify monetization ──────────────────────────
            import info as _info
            sl_url = _info.SHORTLINK_URL
            sl_api = _info.SHORTLINK_API
            user_id = query.from_user.id

            # Premium users and fully-verified users get file directly
            if sl_url and sl_api and not is_premium(user_id):
                vinfo = get_daily_verify_info(user_id)
                if not vinfo['verified']:
                    # User must verify — send shortlink
                    token = make_verify_token(user_id, file_id)
                    temp.VERIFY_TOKENS[token] = {
                        'file_id': file_id,
                        'pre': ident,
                        'user_id': user_id,
                        'expires_at': time.time() + _info.VERIFY_EXPIRE,
                    }
                    bot_link = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
                    short = await get_shortlink(bot_link, sl_url, sl_api)
                    how_url = _info.VERIFY_TUTORIAL or "https://t.me/BackupChannel5211"
                    btn = [
                        [InlineKeyboardButton("🚀 GET FILE", url=short)],
                        [InlineKeyboardButton("📖 How To Bypass", url=how_url)],
                    ]
                    sub_link = _info.SUB_LINK
                    if sub_link:
                        btn.append([InlineKeyboardButton("❗ BUY SUBSCRIPTION — SKIP THIS", url=sub_link)])
                    await query.answer()
                    await client.send_message(
                        chat_id=user_id,
                        text=(
                            f"<b>🎬 Your file is ready!</b>\n\n"
                            f"📄 <code>{title}</code>\n"
                            f"📦 Size: <b>{size}</b>\n\n"
                            f"<b>#VERIFICATION:-</b> {vinfo['count']}/{vinfo['limit']} ✔️\n\n"
                            f"👇 Click <b>GET FILE</b> to bypass the link and get your file."
                        ),
                        reply_markup=InlineKeyboardMarkup(btn),
                        parse_mode=enums.ParseMode.HTML
                    )
                    return

            # Verified / premium / no shortlink → send directly
            await client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=file_id,
                caption=f_caption,
                protect_content=True if ident == "filep" else False
            )
            await query.answer('✅ Check your PM!', show_alert=True)
        except UserIsBlocked:
            await query.answer('Unblock the bot!', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")

    elif query.data.startswith("fsub_retry"):
        # User tapped "I've Joined — Try Again"
        unjoined = await check_fsub(client, query.from_user.id)
        if unjoined:
            ch_names = ", ".join(ch['title'] for ch in unjoined)
            await query.answer(
                f"❌ You still haven't joined: {ch_names}\nPlease join and try again!",
                show_alert=True
            )
            return
        # All joined — figure out what they were trying to get
        deep = query.data.split("#", 1)[1].strip()
        if not deep:
            # No pending file — just show start screen
            await query.answer("✅ Verified! You can now use the bot.", show_alert=True)
            await query.message.delete()
            return
        # deep is e.g. "file_XXXX" or "filep_XXXX"
        try:
            ident, file_id = deep.split("_", 1)
        except ValueError:
            await query.answer("✅ Verified! Search for your movie again.", show_alert=True)
            await query.message.delete()
            return
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('File not found.', show_alert=True)
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
            f_caption = clean_caption(title)
        await query.answer("✅ Access granted!", show_alert=True)
        await query.message.delete()
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'filep' else False
        )

    elif query.data.startswith("checksub"):
        # Legacy handler kept for old inline buttons still in circulation
        unjoined = await check_fsub(client, query.from_user.id)
        if unjoined:
            await query.answer("Please join all required channels first! 😒", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No such file exist.')
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
            except Exception as e:
                logger.exception(e)
        if f_caption is None:
            f_caption = clean_caption(title)
        await query.answer()
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False
        )

    elif query.data == "pages":
        await query.answer()

    elif query.data == "start":
        buttons = [
            [InlineKeyboardButton('➕ Add Me To Your Group ➕', url=f'http://t.me/{temp.U_NAME}?startgroup=true')],
            [
                InlineKeyboardButton('🔍 Inline Search', switch_inline_query_current_chat=''),
                InlineKeyboardButton('📢 Updates', url='https://t.me/BackupChannel5211'),
            ],
            [
                InlineKeyboardButton('📢 Backup', url='https://t.me/backupchannek'),
            ],
            [
                InlineKeyboardButton('❓ Help', callback_data='help'),
                InlineKeyboardButton('ℹ️ About', callback_data='about')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        await query.answer()

    elif query.data == "help":
        buttons = [
            [
                InlineKeyboardButton('Filter', callback_data='filter_help'),
                InlineKeyboardButton('Button', callback_data='button_help'),
            ],
            [
                InlineKeyboardButton('Auto Filter', callback_data='autofilter_help'),
                InlineKeyboardButton('Connection', callback_data='connection_help'),
            ],
            [
                InlineKeyboardButton('Extra Modules', callback_data='extra_help'),
                InlineKeyboardButton('Admin', callback_data='admin_help'),
            ],
            [InlineKeyboardButton('🔙 Back', callback_data='start')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT.format(query.from_user.first_name),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        await query.answer()

    elif query.data == "about":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='start')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(bname=temp.B_NAME or "Miviesfather", uname=temp.U_NAME or "Miviesfather_bot"),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        await query.answer()

    elif query.data == "filter_help":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MANUELFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()

    elif query.data == "button_help":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.BUTTON_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()

    elif query.data == "autofilter_help":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.AUTOFILTER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()

    elif query.data == "connection_help":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CONNECTION_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()

    elif query.data == "extra_help":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.EXTRAMOD_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()

    elif query.data == "admin_help":
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ADMIN_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await query.answer()


async def auto_filter(client, msg, spoll=None):
    if spoll is None:
        if msg.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            return
        if not msg.text:
            return

        if AUTH_GROUPS:
            if msg.chat.id not in AUTH_GROUPS:
                return

        settings = await get_settings(msg.chat.id)
        message = msg
        search = msg.text

        # Ban / disable check
        if msg.from_user and msg.from_user.id in temp.BANNED_USERS:
            return
        if msg.chat.id in temp.BANNED_CHATS:
            return

        files, offset, total_results = await get_search_results(search, offset=0, filter=True)
        if files:
            track_search(search)
            track_weekly_search(search)
        if not files:
            if settings.get('spell_check') and SPELL_CHECK_REPLY:
                return await advantage_spell_chok(msg)
            else:
                return
    else:
        settings = await get_settings(spoll[0] if isinstance(spoll, tuple) else msg.message.chat.id)
        if isinstance(spoll, tuple):
            search, files, offset, total_results = spoll
            message = msg if not isinstance(msg, type(None)) else msg
        else:
            settings = await get_settings(msg.message.chat.id)
            message = msg.message.reply_to_message
            search, files, offset, total_results = spoll

    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [InlineKeyboardButton(
                text=f"[{get_size(file.file_size)}] {clean_caption(file.file_name)}",
                callback_data=f'{pre}#{file.file_id}'
            )]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(text=f"{clean_caption(file.file_name)}", callback_data=f'{pre}#{file.file_id}'),
                InlineKeyboardButton(text=f"{get_size(file.file_size)}", callback_data=f'{pre}#{file.file_id}'),
            ]
            for file in files
        ]

    if isinstance(msg, type(None)):
        return

    if spoll and not isinstance(spoll, tuple):
        message_obj = msg.message.reply_to_message
    else:
        message_obj = msg if not spoll else msg

    # Use the correct message object
    if spoll and isinstance(spoll, tuple):
        message_obj = msg

    if offset != "":
        key = f"{message_obj.chat.id}-{message_obj.id}"
        BUTTONS[key] = search
        req = message_obj.from_user.id if message_obj.from_user else 0
        btn.append([
            InlineKeyboardButton(text=f"🗓 1/{math.ceil(int(total_results) / 10)}", callback_data="pages"),
            InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")
        ])
    else:
        btn.append([InlineKeyboardButton(text="🗓 1/1", callback_data="pages")])

    imdb_data = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    TEMPLATE = settings['template']
    if imdb_data:
        try:
            cap = TEMPLATE.format(
                query=search,
                title=imdb_data['title'],
                votes=imdb_data['votes'],
                aka=imdb_data["aka"],
                seasons=imdb_data["seasons"],
                box_office=imdb_data['box_office'],
                localized_title=imdb_data['localized_title'],
                kind=imdb_data['kind'],
                imdb_id=imdb_data["imdb_id"],
                cast=imdb_data["cast"],
                runtime=imdb_data["runtime"],
                countries=imdb_data["countries"],
                certificates=imdb_data["certificates"],
                languages=imdb_data["languages"],
                director=imdb_data["director"],
                writer=imdb_data["writer"],
                producer=imdb_data["producer"],
                composer=imdb_data["composer"],
                cinematographer=imdb_data["cinematographer"],
                music_team=imdb_data["music_team"],
                distributors=imdb_data["distributors"],
                release_date=imdb_data['release_date'],
                year=imdb_data['year'],
                genres=imdb_data['genres'],
                poster=imdb_data['poster'],
                plot=imdb_data['plot'],
                rating=imdb_data['rating'],
                url=imdb_data['url'],
            )
        except Exception:
            cap = f"Here is what I found for your query {search}"
    else:
        cap = f"Here is what I found for your query {search}"

    if imdb_data and imdb_data.get('poster'):
        try:
            await message_obj.reply_photo(
                photo=imdb_data.get('poster'),
                caption=cap[:1024],
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb_data.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            await message_obj.reply_photo(
                photo=poster, caption=cap[:1024],
                reply_markup=InlineKeyboardMarkup(btn)
            )
        except Exception as e:
            logger.exception(e)
            await message_obj.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await message_obj.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn))

    if spoll and not isinstance(spoll, tuple):
        await msg.message.delete()


async def advantage_spell_chok(msg):
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE
    )
    query = query.strip() + " movie"
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)

    if not g_s:
        k = await msg.reply("I couldn't find any movie in that name.")
        await asyncio.sleep(8)
        await k.delete()
        return

    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)
    gs = list(filter(regex.match, g_s))
    gs_parsed = [re.sub(
        r'\b(\-([a-zA-Z-\s])\-\simdb|(\-\s)?imdb|(\-\s)?wikipedia|\(|\)|\-|reviews|full|all|episode(s)?|film|movie|series)',
        '', i, flags=re.IGNORECASE
    ) for i in gs]

    if not gs_parsed:
        reg = re.compile(r"watch(\s[a-zA-Z0-9_\s\-\(\)]*)*\|.*", re.IGNORECASE)
        for mv in g_s:
            match = reg.match(mv)
            if match:
                gs_parsed.append(match.group(1))

    user = msg.from_user.id if msg.from_user else 0
    movielist = []
    gs_parsed = list(dict.fromkeys(gs_parsed))
    if len(gs_parsed) > 3:
        gs_parsed = gs_parsed[:3]

    if gs_parsed:
        for mov in gs_parsed:
            imdb_s = await get_poster(mov.strip(), bulk=True)
            if imdb_s:
                movielist += [movie.get('title') for movie in imdb_s]

    movielist += [(re.sub(r'(\-|\(|\)|_)', '', i, flags=re.IGNORECASE)).strip() for i in gs_parsed]
    movielist = list(dict.fromkeys(movielist))

    if not movielist:
        k = await msg.reply("I couldn't find anything related to that. Check your spelling")
        await asyncio.sleep(8)
        await k.delete()
        return

    SPELL_CHECK[msg.id] = movielist
    btn = [[InlineKeyboardButton(
        text=movie.strip(),
        callback_data=f"spolling#{user}#{k}",
    )] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="Close", callback_data=f'spolling#{user}#close_spellcheck')])
    await msg.reply(
        "I couldn't find anything related to that\nDid you mean any one of these?",
        reply_markup=InlineKeyboardMarkup(btn)
    )


async def manual_filters(client, message, text=False):
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)
            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")
            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            await client.send_message(group_id, reply_text, disable_web_page_preview=True)
                        else:
                            button = eval(btn)
                            await client.send_message(
                                group_id, reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                    elif btn == "[]":
                        await client.send_cached_media(
                            group_id, fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                    else:
                        button = eval(btn)
                        await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
