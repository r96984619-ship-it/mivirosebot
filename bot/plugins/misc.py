import os
import logging
from pyrogram import Client, filters, enums
from pyrogram.errors.exceptions.bad_request_400 import (
    UserNotParticipant, MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
)
from info import IMDB_TEMPLATE
from utils import extract_user, get_file_id, get_poster, last_online
from datetime import datetime
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        user_id = message.chat.id
        first = message.from_user.first_name
        last = message.from_user.last_name or ""
        username = message.from_user.username
        dc_id = message.from_user.dc_id or ""
        await message.reply_text(
            f"<b>➲ First Name:</b> {first}\n"
            f"<b>➲ Last Name:</b> {last}\n"
            f"<b>➲ Username:</b> {username}\n"
            f"<b>➲ Telegram ID:</b> <code>{user_id}</code>\n"
            f"<b>➲ Data Centre:</b> <code>{dc_id}</code>",
            quote=True
        )
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        _id = f"<b>➲ Chat ID</b>: <code>{message.chat.id}</code>\n"
        if message.reply_to_message:
            _id += (
                f"<b>➲ User ID</b>: <code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
                f"<b>➲ Replied User ID</b>: "
                f"<code>{message.reply_to_message.from_user.id if message.reply_to_message.from_user else 'Anonymous'}</code>\n"
            )
            file_info = get_file_id(message.reply_to_message)
        else:
            _id += f"<b>➲ User ID</b>: <code>{message.from_user.id if message.from_user else 'Anonymous'}</code>\n"
            file_info = get_file_id(message)
        if file_info:
            _id += f"<b>{file_info.message_type}</b>: <code>{file_info.file_id}</code>\n"
        await message.reply_text(_id, quote=True)


@Client.on_message(filters.command(["info"]))
async def who_is(client, message):
    status_message = await message.reply_text("`Fetching user info...`")
    await status_message.edit("`Processing user info...`")
    from_user = None
    from_user_id, _ = extract_user(message)
    try:
        from_user = await client.get_users(from_user_id)
    except Exception as error:
        await status_message.edit(str(error))
        return
    if from_user is None:
        return await status_message.edit("no valid user_id / message specified")

    message_out_str = ""
    message_out_str += f"<b>➲First Name:</b> {from_user.first_name}\n"
    last_name = from_user.last_name or "<b>None</b>"
    message_out_str += f"<b>➲Last Name:</b> {last_name}\n"
    message_out_str += f"<b>➲Telegram ID:</b> <code>{from_user.id}</code>\n"
    username = from_user.username or "<b>None</b>"
    dc_id = from_user.dc_id or "[User Doesn't Have A Valid DP]"
    message_out_str += f"<b>➲Data Centre:</b> <code>{dc_id}</code>\n"
    message_out_str += f"<b>➲User Name:</b> @{username}\n"
    message_out_str += f"<b>➲User Link:</b> <a href='tg://user?id={from_user.id}'><b>Click Here</b></a>\n"

    if message.chat.type in [enums.ChatType.SUPERGROUP, enums.ChatType.CHANNEL]:
        try:
            chat_member_p = await message.chat.get_member(from_user.id)
            joined_date = (
                chat_member_p.joined_date or datetime.now()
            ).strftime("%Y.%m.%d %H:%M:%S")
            message_out_str += f"<b>➲Joined this Chat on:</b> <code>{joined_date}</code>\n"
        except UserNotParticipant:
            pass

    chat_photo = from_user.photo
    buttons = [[InlineKeyboardButton('🔐 Close', callback_data='close_data')]]
    reply_markup = InlineKeyboardMarkup(buttons)

    if chat_photo:
        local_user_photo = await client.download_media(message=chat_photo.big_file_id)
        await message.reply_photo(
            photo=local_user_photo,
            quote=True,
            reply_markup=reply_markup,
            caption=message_out_str,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
        os.remove(local_user_photo)
    else:
        await message.reply_text(
            text=message_out_str,
            reply_markup=reply_markup,
            quote=True,
            parse_mode=enums.ParseMode.HTML,
            disable_notification=True
        )
    await status_message.delete()


@Client.on_message(filters.command(["imdb", 'search']))
async def imdb_search(client, message):
    if ' ' in message.text:
        k = await message.reply('Searching IMDb')
        r, title = message.text.split(None, 1)
        movies = await get_poster(title, bulk=True)
        if not movies:
            return await k.edit("No results Found")
        btn = [
            [InlineKeyboardButton(
                text=f"{movie.get('title')} - {movie.get('year')}",
                callback_data=f"imdb#{movie.movieID}",
            )]
            for movie in movies
        ]
        await k.edit('Here is what I found on IMDb', reply_markup=InlineKeyboardMarkup(btn))
    else:
        await message.reply('Give me a movie / series Name')


@Client.on_callback_query(filters.regex('^imdb'))
async def imdb_callback(bot: Client, quer_y: CallbackQuery):
    i, movie = quer_y.data.split('#')
    await quer_y.answer('Fetching IMDb data...', show_alert=False)
    imdb = await get_poster(query=movie, id=True)

    if not imdb:
        await quer_y.message.edit("❌ No IMDb results found.")
        return

    btn = [
        [InlineKeyboardButton(text="🎬 IMDb Page", url=imdb['url'])],
    ]
    if imdb.get('trailer'):
        btn[0].append(InlineKeyboardButton(text="▶️ Trailer", url=imdb['trailer']))

    try:
        caption = IMDB_TEMPLATE.format(
            query=imdb['title'],
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
        )
    except Exception as e:
        logger.exception(e)
        caption = f"<b>🎬 {imdb.get('title')}</b>\n\n⭐️ Rating: {imdb.get('rating')}/10\n🎭 {imdb.get('genres')}"

    if imdb.get('poster'):
        try:
            await quer_y.message.reply_photo(
                photo=imdb['poster'],
                caption=caption[:1024],
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML
            )
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            poster = imdb['poster'].replace('.jpg', "._V1_UX360.jpg")
            try:
                await quer_y.message.reply_photo(
                    photo=poster,
                    caption=caption[:1024],
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception:
                await quer_y.message.reply(
                    caption[:4096],
                    reply_markup=InlineKeyboardMarkup(btn),
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
        except Exception as e:
            logger.exception(e)
            await quer_y.message.reply(
                caption[:4096],
                reply_markup=InlineKeyboardMarkup(btn),
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        await quer_y.message.delete()
    else:
        await quer_y.message.edit(
            caption[:4096],
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
