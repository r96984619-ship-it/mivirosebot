"""
persistence.py — Save and restore temp state across bot restarts.

Saves to: bot/data/state.json
What survives restarts:
  - PREMIUM_USERS      (set of user IDs with premium access)
  - REFERRAL_CODES     (code → user_id mapping)
  - REFERRAL_COUNTS    (user_id → invite count)
  - REFERRAL_BY        (new_user_id → referrer_id, prevents double-count)
  - REFERRAL_REWARDED  (set of user_ids notified per milestone)
  - VERIFY_STATS       (daily/weekly/total verify counts)
"""

import json
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

_DATA_DIR  = os.path.join(os.path.dirname(__file__), 'data')
STATE_FILE = os.path.join(_DATA_DIR, 'state.json')
SAVE_INTERVAL = 300  # auto-save every 5 minutes


def _ensure_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


# ── Load ──────────────────────────────────────────────────────────────────────

def load_state():
    """
    Load persisted state into temp at startup (synchronous).
    Call this BEFORE bot.start() so state is ready when handlers fire.
    """
    from utils import temp

    _ensure_dir()
    if not os.path.exists(STATE_FILE):
        logger.info("persistence: no state file found — starting fresh.")
        return

    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"persistence: failed to read state file: {e} — starting fresh.")
        return

    try:
        # PREMIUM_USERS — stored as list of ints
        temp.PREMIUM_USERS = set(int(x) for x in data.get('premium_users', []))

        # REFERRAL_CODES — code(str) → user_id(int)
        temp.REFERRAL_CODES = {
            str(k): int(v)
            for k, v in data.get('referral_codes', {}).items()
        }

        # REFERRAL_COUNTS — user_id(int) → count(int)
        temp.REFERRAL_COUNTS = {
            int(k): int(v)
            for k, v in data.get('referral_counts', {}).items()
        }

        # REFERRAL_BY — new_user_id(int) → referrer_id(int)
        temp.REFERRAL_BY = {
            int(k): int(v)
            for k, v in data.get('referral_by', {}).items()
        }

        # REFERRAL_REWARDED — set of ints
        temp.REFERRAL_REWARDED = set(int(x) for x in data.get('referral_rewarded', []))

        # VERIFY_STATS — nested dict, keys stay as strings (dates/week keys)
        saved_stats = data.get('verify_stats', {})
        temp.VERIFY_STATS = {
            'daily':  dict(saved_stats.get('daily', {})),
            'weekly': dict(saved_stats.get('weekly', {})),
            'total':  int(saved_stats.get('total', 0)),
        }

        counts = {
            'premium': len(temp.PREMIUM_USERS),
            'referrers': len(temp.REFERRAL_COUNTS),
            'referrals': sum(temp.REFERRAL_COUNTS.values()),
            'verify_total': temp.VERIFY_STATS['total'],
        }
        logger.info(
            f"persistence: state loaded ✅ — "
            f"{counts['premium']} premium users, "
            f"{counts['referrers']} referrers, "
            f"{counts['referrals']} total referrals, "
            f"{counts['verify_total']} verifications."
        )

    except Exception as e:
        logger.warning(f"persistence: error applying loaded state: {e}")


# ── Save ──────────────────────────────────────────────────────────────────────

async def save_state():
    """
    Write current temp state to disk (async, non-blocking via run_in_executor).
    """
    from utils import temp

    _ensure_dir()
    data = {
        'premium_users':    list(temp.PREMIUM_USERS),
        'referral_codes':   {str(k): v for k, v in temp.REFERRAL_CODES.items()},
        'referral_counts':  {str(k): v for k, v in temp.REFERRAL_COUNTS.items()},
        'referral_by':      {str(k): v for k, v in temp.REFERRAL_BY.items()},
        'referral_rewarded': list(temp.REFERRAL_REWARDED),
        'verify_stats': {
            'daily':  dict(temp.VERIFY_STATS.get('daily', {})),
            'weekly': dict(temp.VERIFY_STATS.get('weekly', {})),
            'total':  temp.VERIFY_STATS.get('total', 0),
        },
    }
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_json, data)
        logger.debug("persistence: state saved.")
    except Exception as e:
        logger.warning(f"persistence: save failed: {e}")


def _write_json(data: dict):
    """Write atomically via temp file so a crash mid-write never corrupts."""
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, STATE_FILE)  # atomic on POSIX


def save_state_sync():
    """Synchronous save — use only in shutdown handlers where event loop is gone."""
    from utils import temp

    _ensure_dir()
    data = {
        'premium_users':    list(temp.PREMIUM_USERS),
        'referral_codes':   {str(k): v for k, v in temp.REFERRAL_CODES.items()},
        'referral_counts':  {str(k): v for k, v in temp.REFERRAL_COUNTS.items()},
        'referral_by':      {str(k): v for k, v in temp.REFERRAL_BY.items()},
        'referral_rewarded': list(temp.REFERRAL_REWARDED),
        'verify_stats': {
            'daily':  dict(temp.VERIFY_STATS.get('daily', {})),
            'weekly': dict(temp.VERIFY_STATS.get('weekly', {})),
            'total':  temp.VERIFY_STATS.get('total', 0),
        },
    }
    try:
        _write_json(data)
        logger.info("persistence: state saved (sync).")
    except Exception as e:
        logger.warning(f"persistence: sync save failed: {e}")


# ── Auto-save loop ────────────────────────────────────────────────────────────

async def auto_save_loop():
    """
    Background coroutine — saves state every SAVE_INTERVAL seconds.
    Start with: asyncio.get_running_loop().create_task(auto_save_loop())
    """
    logger.info(f"persistence: auto-save loop started (every {SAVE_INTERVAL}s).")
    while True:
        await asyncio.sleep(SAVE_INTERVAL)
        await save_state()
