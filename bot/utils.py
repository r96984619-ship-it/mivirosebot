import logging
import asyncio
import re
import os
import requests
from typing import Union, List
from datetime import datetime
from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.types import Message, InlineKeyboardButton
from pyrogram import enums
from info import AUTH_CHANNEL, LONG_IMDB_DESCRIPTION, MAX_LIST_ELM
from database.users_chats_db import db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BTN_URL_REGEX = re.compile(
    r"(\[([^\[]+?)\]\((buttonurl|buttonalert):(?:/{0,2})(.+?)(:same)?\))"
)

BANNED = {}
SMART_OPEN = '\u201c'
SMART_CLOSE = '\u201d'
START_CHAR = ('\'', '"', SMART_OPEN)


import hashlib
import time

# ── Shortlink helpers ─────────────────────────────────────────────────────────

async def get_shortlink(url: str, api_url: str, api_key: str) -> str:
    """Shorten a URL using any mdisk-compatible shortener API."""
    import aiohttp
    try:
        api_base = api_url.rstrip('/')
        if not api_base.startswith('http'):
            api_base = 'https://' + api_base
        endpoint = f"{api_base}/api?api={api_key}&url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                short = (
                    data.get('shortenedUrl')
                    or data.get('short_url')
                    or data.get('shortedUrl')
                    or data.get('url')
                )
                if short:
                    return short
    except Exception:
        pass
    return url   # fallback: return original url if shortener fails


def make_verify_token(user_id: int, file_id: str) -> str:
    """Create a unique one-time token for file verification."""
    raw = f"{user_id}-{file_id}-{time.time()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def clean_caption(text: str) -> str:
    """Replace external @channel watermarks; preserve both owner channels."""
    if not text:
        return text
    return re.sub(
        r'@(?!(?:BackupChannel5211|backupchannek)(?:\b|$))([A-Za-z][A-Za-z0-9_]*)',
        '@BackupChannel5211',
        text,
        flags=re.IGNORECASE
    )


class temp(object):
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    CURRENT = int(os.environ.get("SKIP", 2))
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None
    SETTINGS = {}
    VERIFY_TOKENS = {}    # token -> {file_id, pre, expires_at, user_id}
    DAILY_VERIFY = {}     # user_id -> {date: 'YYYY-MM-DD', count: N}
    PREMIUM_USERS = set() # user_ids with premium (bypass verify)
    MOST_SEARCHED = {}    # movie_name -> count (all-time)
    WEEKLY_SEARCHES = {} # week_key -> {movie_name -> count}
    VERIFY_STATS = {
        'daily': {},   # 'YYYY-MM-DD' -> count
        'weekly': {},  # 'YYYY-Www'   -> count
        'total': 0,
    }
    # ── Referral system ───────────────────────────────────────────────────────
    REFERRAL_CODES   = {}  # code(str)          → user_id(int)
    REFERRAL_COUNTS  = {}  # user_id(int)        → invite count(int)
    REFERRAL_BY      = {}  # new_user_id(int)    → referrer_id(int)  (prevents double-count)
    REFERRAL_REWARDED = set()  # user_ids already notified of each 10-multiple milestone
    BOT_START_TIME = time.time()  # set at import; overwritten in Bot.start()


# ── Greeting / Verify helpers ─────────────────────────────────────────────────

def get_time_greeting() -> str:
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        return "GOOD MORNING"
    elif hour < 17:
        return "GOOD AFTERNOON"
    else:
        return "GOOD EVENING"


def get_daily_verify_info(user_id: int) -> dict:
    """Return {count, verified} for user's current day."""
    from datetime import date
    import info as _info
    today = str(date.today())
    entry = temp.DAILY_VERIFY.get(user_id)
    if not entry or entry.get('date') != today:
        entry = {'date': today, 'count': 0}
        temp.DAILY_VERIFY[user_id] = entry
    count = entry['count']
    limit = _info.VERIFY_DAILY_LIMIT
    return {'count': count, 'limit': limit, 'verified': count >= limit}


def mark_verified(user_id: int):
    """Increment user's daily verify count and global stats."""
    from datetime import date, datetime
    today = str(date.today())
    entry = temp.DAILY_VERIFY.get(user_id)
    if not entry or entry.get('date') != today:
        entry = {'date': today, 'count': 0}
    entry['count'] += 1
    temp.DAILY_VERIFY[user_id] = entry
    # ── Global stats ──────────────────────────────────────────────────────────
    iso = datetime.utcnow().isocalendar()
    week_key = f"{iso[0]}-W{iso[1]:02d}"
    temp.VERIFY_STATS['daily'][today] = temp.VERIFY_STATS['daily'].get(today, 0) + 1
    temp.VERIFY_STATS['weekly'][week_key] = temp.VERIFY_STATS['weekly'].get(week_key, 0) + 1
    temp.VERIFY_STATS['total'] += 1
    # Keep only last 8 weeks of daily data to cap memory usage
    all_days = sorted(temp.VERIFY_STATS['daily'].keys())
    if len(all_days) > 56:
        for old_day in all_days[:-56]:
            del temp.VERIFY_STATS['daily'][old_day]


def _schedule_save():
    """Fire-and-forget: schedule a persistence save from sync code."""
    try:
        import asyncio, persistence as _p
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_p.save_state())
    except Exception:
        pass


def get_verify_stats() -> dict:
    """Return a snapshot of verification stats for /shortlink_stats."""
    from datetime import date, datetime
    today = str(date.today())
    iso = datetime.utcnow().isocalendar()
    week_key = f"{iso[0]}-W{iso[1]:02d}"
    today_count = temp.VERIFY_STATS['daily'].get(today, 0)
    week_count = temp.VERIFY_STATS['weekly'].get(week_key, 0)
    total = temp.VERIFY_STATS['total']
    # Yesterday for comparison
    from datetime import timedelta
    yesterday = str(date.today() - timedelta(days=1))
    yesterday_count = temp.VERIFY_STATS['daily'].get(yesterday, 0)
    return {
        'today': today_count,
        'yesterday': yesterday_count,
        'this_week': week_count,
        'total': total,
        'week_key': week_key,
        'date': today,
    }


def is_premium(user_id: int) -> bool:
    return user_id in temp.PREMIUM_USERS


# ── Referral helpers ──────────────────────────────────────────────────────────

def get_refer_code(user_id: int) -> str:
    """Get or create a unique 8-char referral code for a user."""
    import hashlib
    # Check if code already exists for this user
    for code, uid in temp.REFERRAL_CODES.items():
        if uid == user_id:
            return code
    # Create new code
    raw = f"ref-{user_id}-{time.time()}"
    code = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
    # Avoid collisions
    while code in temp.REFERRAL_CODES:
        raw += "x"
        code = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
    temp.REFERRAL_CODES[code] = user_id
    return code


def process_refer(new_user_id: int, code: str):
    """
    Record a referral when a new user starts via ref_CODE.
    Returns (referrer_id, milestone_hit) or (None, False).
    - Ignores self-referral.
    - Ignores if new_user already came via any referral link (prevents gaming).
    """
    import info as _info
    referrer_id = temp.REFERRAL_CODES.get(code)
    if not referrer_id:
        return None, False
    if referrer_id == new_user_id:
        return None, False                       # can't refer yourself
    if new_user_id in temp.REFERRAL_BY:
        return referrer_id, False                # already counted from another link
    # Record it
    temp.REFERRAL_BY[new_user_id] = referrer_id
    temp.REFERRAL_COUNTS[referrer_id] = temp.REFERRAL_COUNTS.get(referrer_id, 0) + 1
    count = temp.REFERRAL_COUNTS[referrer_id]
    threshold = _info.REFER_PREMIUM_THRESHOLD
    # Check if they just hit a new milestone (every N invites)
    milestone_hit = (count % threshold == 0)
    # Persist state after every referral event
    try:
        import asyncio, persistence as _p
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_p.save_state())
    except Exception:
        pass
    return referrer_id, milestone_hit


def get_refer_stats(user_id: int) -> dict:
    """Return referral stats for a user."""
    import info as _info
    code = get_refer_code(user_id)
    count = temp.REFERRAL_COUNTS.get(user_id, 0)
    threshold = _info.REFER_PREMIUM_THRESHOLD
    remaining = threshold - (count % threshold) if count % threshold != 0 else 0
    return {
        'code': code,
        'count': count,
        'threshold': threshold,
        'remaining': remaining,
        'milestones': count // threshold,
    }


def get_refer_leaderboard(limit: int = 10) -> list:
    """Return top referrers sorted by invite count."""
    ranked = sorted(temp.REFERRAL_COUNTS.items(), key=lambda x: x[1], reverse=True)
    return ranked[:limit]


def track_search(query: str):
    """Increment search counter for a query."""
    key = query.strip().lower().title()
    temp.MOST_SEARCHED[key] = temp.MOST_SEARCHED.get(key, 0) + 1


def get_most_searched(top_n: int = 10) -> list:
    """Return list of (title, count) sorted by count desc."""
    return sorted(temp.MOST_SEARCHED.items(), key=lambda x: x[1], reverse=True)[:top_n]


def _current_week_key() -> str:
    """Return ISO week key like '2026-W24'."""
    from datetime import datetime
    d = datetime.utcnow().isocalendar()
    return f"{d[0]}-W{d[1]:02d}"


def track_weekly_search(query: str):
    """Increment weekly search counter for a query."""
    week = _current_week_key()
    key = query.strip().lower().title()
    if week not in temp.WEEKLY_SEARCHES:
        temp.WEEKLY_SEARCHES[week] = {}
    temp.WEEKLY_SEARCHES[week][key] = temp.WEEKLY_SEARCHES[week].get(key, 0) + 1
    # Keep only the last 2 weeks to avoid unbounded memory growth
    for old_week in [k for k in temp.WEEKLY_SEARCHES if k != week and k != _prev_week_key()]:
        del temp.WEEKLY_SEARCHES[old_week]


def _prev_week_key() -> str:
    """Return ISO week key for last week."""
    from datetime import datetime, timedelta
    d = (datetime.utcnow() - timedelta(weeks=1)).isocalendar()
    return f"{d[0]}-W{d[1]:02d}"


def get_weekly_trending(top_n: int = 10) -> list:
    """Return list of (title, count) for the current week, sorted by count desc."""
    week = _current_week_key()
    week_data = temp.WEEKLY_SEARCHES.get(week, {})
    return sorted(week_data.items(), key=lambda x: x[1], reverse=True)[:top_n]


# ── IMDb helpers ──────────────────────────────────────────────────────────────

_IMDB_AVAILABLE = False
try:
    from imdb import IMDb as _IMDb
    imdb = _IMDb()
    _IMDB_AVAILABLE = True
except Exception:
    imdb = None

def _mock_poster(query):
    """Return a stub IMDb result when the real library is unavailable."""
    return {
        'title': query or 'Unknown',
        'votes': 'N/A',
        'aka': 'N/A',
        'seasons': None,
        'box_office': None,
        'localized_title': query or 'Unknown',
        'kind': 'movie',
        'imdb_id': 'tt0000000',
        'cast': 'N/A',
        'runtime': 'N/A',
        'countries': 'N/A',
        'certificates': 'N/A',
        'languages': 'N/A',
        'director': 'N/A',
        'writer': 'N/A',
        'producer': 'N/A',
        'composer': 'N/A',
        'cinematographer': 'N/A',
        'music_team': 'N/A',
        'distributors': 'N/A',
        'release_date': 'N/A',
        'year': 'N/A',
        'genres': 'N/A',
        'poster': None,
        'plot': 'IMDb lookup is not available in this environment.',
        'rating': 'N/A',
        'url': 'https://www.imdb.com',
        'movieID': '0000000',
    }


async def is_subscribed(bot, query):
    """Legacy single-channel check (kept for backward compat)."""
    try:
        user = await bot.get_chat_member(AUTH_CHANNEL, query.from_user.id)
    except UserNotParticipant:
        return False
    except Exception as e:
        logger.exception(e)
        return False
    return user.status not in ['kicked', 'left']


async def check_fsub(bot, user_id: int) -> list:
    """
    Check all configured force-subscribe channels.
    Returns a list of dicts for every channel the user has NOT joined:
        [{'id': -100xxx, 'title': 'Channel Name', 'invite_link': 'https://...'}]
    Empty list means the user has joined all channels (access granted).
    """
    import info as _info
    channels = [c for c in [_info.AUTH_CHANNEL, _info.FSUB_2, _info.FSUB_3] if c]
    unjoined = []
    for ch_id in channels:
        try:
            member = await bot.get_chat_member(ch_id, user_id)
            if member.status in ['kicked', 'left']:
                raise UserNotParticipant
        except UserNotParticipant:
            try:
                chat = await bot.get_chat(ch_id)
                title = chat.title or str(ch_id)
                try:
                    inv = await bot.create_chat_invite_link(ch_id)
                    link = inv.invite_link
                except Exception:
                    link = chat.invite_link or f"https://t.me/c/{str(ch_id).replace('-100', '')}"
            except Exception:
                title = str(ch_id)
                link = f"https://t.me/c/{str(ch_id).replace('-100', '')}"
            unjoined.append({'id': ch_id, 'title': title, 'invite_link': link})
        except Exception as e:
            logger.warning(f"FSub check error for {ch_id}: {e}")
    return unjoined


async def get_poster(query, bulk=False, id=False, file=None):
    if not _IMDB_AVAILABLE:
        if bulk:
            stub = type('MockMovie', (), {
                'get': lambda self, k, d=None: d,
                'movieID': '0000000',
                'data': {'title': query, 'year': 'N/A'},
            })()
            stub.get = lambda k, d=None: {'title': query, 'year': 'N/A'}.get(k, d)
            stub.movieID = '0000000'
            return [stub]
        return _mock_poster(query)

    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
        else:
            year = None

        try:
            movieid = imdb.search_movie(title.lower(), results=10)
        except Exception:
            return _mock_poster(query) if not bulk else []

        if not movieid:
            return None
        if year:
            filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
            if not filtered:
                filtered = movieid
        else:
            filtered = movieid
        movieid_list = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
        if not movieid_list:
            movieid_list = filtered
        if bulk:
            return movieid_list
        movieid = movieid_list[0].movieID
    else:
        movieid = query

    try:
        movie = imdb.get_movie(movieid)
    except Exception:
        return _mock_poster(str(query))

    if movie.get("original air date"):
        date = movie["original air date"]
    elif movie.get("year"):
        date = movie.get("year")
    else:
        date = "N/A"

    plot = ""
    if not LONG_IMDB_DESCRIPTION:
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
    else:
        plot = movie.get('plot outline')
    if plot and len(plot) > 800:
        plot = plot[0:800] + "..."

    return {
        'title': movie.get('title'),
        'votes': movie.get('votes'),
        'aka': list_to_str(movie.get("akas")),
        'seasons': movie.get("number of seasons"),
        'box_office': movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        'imdb_id': f"tt{movie.get('imdbID')}",
        'cast': list_to_str(movie.get("cast")),
        'runtime': list_to_str(movie.get("runtimes")),
        'countries': list_to_str(movie.get("countries")),
        'certificates': list_to_str(movie.get("certificates")),
        'languages': list_to_str(movie.get("languages")),
        'director': list_to_str(movie.get("director")),
        'writer': list_to_str(movie.get("writer")),
        'producer': list_to_str(movie.get("producer")),
        'composer': list_to_str(movie.get("composer")),
        'cinematographer': list_to_str(movie.get("cinematographer")),
        'music_team': list_to_str(movie.get("music department")),
        'distributors': list_to_str(movie.get("distributors")),
        'release_date': date,
        'year': movie.get('year'),
        'genres': list_to_str(movie.get("genres")),
        'poster': movie.get('full-size cover url'),
        'plot': plot,
        'rating': str(movie.get("rating")),
        'url': f'https://www.imdb.com/title/tt{movieid}',
    }


async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logger.info(f"{user_id} - Removed from Database, deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        logger.info(f"{user_id} - Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logger.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception:
        return False, "Error"


async def search_gagala(text):
    try:
        from bs4 import BeautifulSoup
        usr_agent = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
            )
        }
        text = text.replace(" ", '+')
        url = f'https://www.google.com/search?q={text}'
        response = requests.get(url, headers=usr_agent, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        titles = soup.find_all('h3')
        return [title.getText() for title in titles]
    except Exception:
        return []


async def get_settings(group_id):
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS[group_id] = settings
    return settings


async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current[key] = value
    temp.SETTINGS[group_id] = current
    await db.update_settings(group_id, current)


def get_size(size):
    """Get size in readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])


def get_readable_time(seconds: int) -> str:
    """Convert seconds to a human-readable string like '2h 05m 30s'."""
    result = ""
    (d, remainder) = divmod(seconds, 86400)
    (h, remainder) = divmod(remainder, 3600)
    (m, s) = divmod(remainder, 60)
    if d:
        result += f"{d}d "
    if h:
        result += f"{h}h "
    if m:
        result += f"{m}m "
    result += f"{s}s"
    return result.strip()


def split_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def get_file_id(msg: Message):
    if msg.media:
        for message_type in (
            "photo", "animation", "audio", "document",
            "video", "video_note", "voice", "sticker"
        ):
            obj = getattr(msg, message_type)
            if obj:
                setattr(obj, "message_type", message_type)
                return obj


def extract_user(message: Message) -> Union[int, str]:
    user_id = None
    user_first_name = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_first_name = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        if (
            len(message.entities) > 1
            and message.entities[1].type == enums.MessageEntityType.TEXT_MENTION
        ):
            required_entity = message.entities[1]
            user_id = required_entity.user.id
            user_first_name = required_entity.user.first_name
        else:
            user_id = message.command[1]
            user_first_name = user_id
        try:
            user_id = int(user_id)
        except ValueError:
            pass
    else:
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
    return (user_id, user_first_name)


def list_to_str(k):
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    elif MAX_LIST_ELM:
        k = k[:int(MAX_LIST_ELM)]
        return ' '.join(f'{elem}, ' for elem in k)
    else:
        return ' '.join(f'{elem}, ' for elem in k)


def last_online(from_user):
    time = ""
    if from_user.is_bot:
        time += "🤖 Bot :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        time += "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        time += "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        time += "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        time += "A long time ago :("
    elif from_user.status == enums.UserStatus.ONLINE:
        time += "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        time += from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return time


def split_quotes(text: str) -> List:
    if not any(text.startswith(char) for char in START_CHAR):
        return text.split(None, 1)
    counter = 1
    while counter < len(text):
        if text[counter] == "\\":
            counter += 1
        elif text[counter] == text[0] or (text[0] == SMART_OPEN and text[counter] == SMART_CLOSE):
            break
        counter += 1
    else:
        return text.split(None, 1)

    key = remove_escapes(text[1:counter].strip())
    rest = text[counter + 1:].strip()
    if not key:
        key = text[0] + text[0]
    return list(filter(None, [key, rest]))


def parser(text, keyword):
    if "buttonalert" in text:
        text = text.replace("\n", "\\n").replace("\t", "\\t")
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    ))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}"
                    )])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                ))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", "")
                )])
        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except Exception:
        return note_data, buttons, None


def remove_escapes(text: str) -> str:
    res = ""
    is_escaped = False
    for counter in range(len(text)):
        if is_escaped:
            res += text[counter]
            is_escaped = False
        elif text[counter] == "\\":
            is_escaped = True
        else:
            res += text[counter]
    return res


def humanbytes(size):
    if not size:
        return ""
    power = 2 ** 10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'
