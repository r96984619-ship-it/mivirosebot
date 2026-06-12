import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS
from utils import get_refer_code, get_refer_stats, get_refer_leaderboard, temp, is_premium

logger = logging.getLogger(__name__)


@Client.on_message(filters.command('refer') & filters.incoming)
async def refer_cmd(bot, message):
    import info as _info
    user_id = message.from_user.id
    stats = get_refer_stats(user_id)
    code   = stats['code']
    count  = stats['count']
    threshold  = stats['threshold']
    remaining  = stats['remaining']
    milestones = stats['milestones']

    uname = getattr(temp, 'U_NAME', None) or 'Miviesfather_bot'
    link  = f"https://t.me/{uname}?start=ref_{code}"

    # Progress bar  ████░░░░░░  10 blocks
    filled  = min(10, int((count % threshold) / threshold * 10)) if threshold > 0 else 10
    bar     = '█' * filled + '░' * (10 - filled)

    if remaining == 0 and count > 0:
        progress_line = f"{bar}  ✅ Milestone reached!"
    else:
        progress_line = f"{bar}  {count % threshold}/{threshold}"

    premium_note = ""
    if is_premium(user_id):
        premium_note = "\n\n💎 You currently have <b>Premium</b> status!"

    if milestones > 0:
        milestone_note = f"\n🏆 Total milestones hit: <b>{milestones}</b> (earned Premium {milestones}x)"
    else:
        milestone_note = ""

    text = (
        f"<b>🎁 Your Referral Link</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Share this link — every person who joins via your link counts toward FREE Premium.\n\n"
        f"<b>📊 Your Progress:</b>\n"
        f"{progress_line}\n"
        f"👥 Total invited: <b>{count}</b>\n"
        f"🎯 Goal: <b>{threshold} invites = 1 month Premium</b>\n"
        f"{milestone_note}"
        f"{premium_note}\n\n"
        f"<i>Tip: share in groups, stories, and other channels for faster growth!</i>"
    )
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share My Link", url=f"https://t.me/share/url?url={link}&text=Join+and+get+movies+free!")],
    ])
    await message.reply(text, reply_markup=btn, parse_mode="html", disable_web_page_preview=True)


@Client.on_message(filters.command('refer_stats'))
async def refer_stats_cmd(bot, message):
    from plugins.shortlink import _admin_check
    if not await _admin_check(message): return
    import info as _info
    board = get_refer_leaderboard(15)
    total_referrals = sum(temp.REFERRAL_COUNTS.values())
    total_referrers = len(temp.REFERRAL_COUNTS)

    if not board:
        return await message.reply(
            "📊 <b>Referral Stats</b>\n\nNo referrals recorded yet.\nUsers earn Premium by inviting friends via /refer.",
            parse_mode="html"
        )

    rows = []
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    for rank, (uid, count) in enumerate(board, 1):
        medal = medals.get(rank, f"{rank}.")
        prem  = '💎' if is_premium(uid) else ''
        rows.append(f"{medal} <code>{uid}</code> — <b>{count}</b> invites {prem}")

    text = (
        f"<b>📊 Referral Leaderboard</b>\n\n"
        f"👥 Total referrers: <b>{total_referrers}</b>\n"
        f"🔗 Total referrals: <b>{total_referrals}</b>\n"
        f"🎯 Threshold for Premium: <b>{_info.REFER_PREMIUM_THRESHOLD}</b> invites\n\n"
        + "\n".join(rows)
        + "\n\n<i>Counts reset on bot restart (in-memory).</i>"
    )
    await message.reply(text, parse_mode="html")


@Client.on_message(filters.command('set_refer_threshold'))
async def set_refer_threshold_cmd(bot, message):
    from plugins.shortlink import _admin_check
    if not await _admin_check(message): return
    import info as _info
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.reply(
            "**Usage:** `/set_refer_threshold <number>`\n\n"
            "**Example:** `/set_refer_threshold 5` — users earn Premium after 5 invites\n\n"
            f"Current threshold: **{_info.REFER_PREMIUM_THRESHOLD}**",
            parse_mode="markdown"
        )
    new_val = int(parts[1])
    if new_val < 1:
        return await message.reply("❌ Threshold must be at least 1.")
    _info.REFER_PREMIUM_THRESHOLD = new_val
    await message.reply(
        f"✅ Referral threshold updated to **{new_val}** invites.\n\n"
        f"Users now need to invite **{new_val}** people to earn Premium.",
        parse_mode="markdown"
    )
