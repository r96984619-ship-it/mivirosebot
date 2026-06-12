# Miviesfather Telegram Bot — Agent Handoff Notes

> **Purpose:** Complete technical context for any AI agent or developer taking over this project. Read this before touching any file.

---

## Project Overview

**Bot name:** Miviesfather Bot  
**GitHub repo:** `r96984619-ship-it/Mediafilterbot`  
**Purpose:** Telegram movie/media bot — users search for movies, get direct download/stream links. Features include shortlink monetization, FSub (forced subscribe) gates, IMDb search, premium bypass, referral system, and admin controls.

---

## How to Make Changes

### ⚠️ Git CLI is BLOCKED on Replit
You **cannot** use `git commit`, `git push`, etc. You must push via the **GitHub API** using the 3-step flow:

```
1. Create blobs (one per changed file)
2. Create a new tree (base_tree = current HEAD tree SHA)
3. Create commit (parent = HEAD SHA, tree = new tree SHA)
4. PATCH refs/heads/main with new commit SHA
```

Token is in `$GITHUB_PERSONAL_ACCESS_TOKEN` env var. Repo: `r96984619-ship-it/Mediafilterbot`.

**IMPORTANT:** The repo's file paths are relative to `bot/` (not `tgbot/bot/`) because the repo root is the `bot/` folder.  
So: local `tgbot/bot/utils.py` → GitHub path `bot/utils.py`  
And: local `tgbot/bot/plugins/referral.py` → GitHub path `bot/plugins/referral.py`

Example push script (run from bash):
```bash
REPO="r96984619-ship-it/Mediafilterbot"
TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN"

# Get current HEAD
HEAD_SHA=$(curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$REPO/git/ref/heads/main" | \
  node -e "const d=require('fs').readFileSync('/dev/stdin','utf8'); console.log(JSON.parse(d).object.sha)")

TREE_SHA=$(curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$REPO/git/commits/$HEAD_SHA" | \
  node -e "const d=require('fs').readFileSync('/dev/stdin','utf8'); console.log(JSON.parse(d).tree.sha)")

# Create blob for each file
FILE_SHA=$(curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  "https://api.github.com/repos/$REPO/git/blobs" \
  -d "{\"content\":\"$(base64 -w 0 /path/to/local/file.py)\",\"encoding\":\"base64\"}" | \
  node -e "const d=require('fs').readFileSync('/dev/stdin','utf8'); console.log(JSON.parse(d).sha)")

# Create tree + commit + update ref (see previous sessions for full example)
```

### Bot Workflow
- **Workflow name:** `Telegram Bot`
- **Command:** `cd tgbot/bot && python bot.py`
- **Restart command:** Use `restart_workflow "Telegram Bot"` via Replit agent tools

### Syntax check before restart:
```bash
cd /home/runner/workspace/tgbot/bot
python -m py_compile utils.py info.py Script.py plugins/commands.py plugins/referral.py
```

---

## Repository / File Structure

```
tgbot/
└── bot/                         ← all source files here
    ├── bot.py                   ← entry point, loads all plugins
    ├── info.py                  ← config/env vars (source of truth for all settings)
    ├── utils.py                 ← temp class (in-memory state), helper functions
    ├── Script.py                ← all user-facing text/help strings
    ├── database/
    │   └── users_chats_db.py   ← user/chat DB (MongoDB or mock)
    └── plugins/
        ├── commands.py         ← /start handler, pm_text_redirect, main routing
        ├── referral.py         ← /refer, /refer_stats, /set_refer_threshold  ← NEW
        ├── shortlink.py        ← shortlink admin commands
        ├── filters.py          ← file filtering
        ├── fsub.py             ← forced subscription logic
        └── ...
```

---

## Key Architecture Details

### `temp` class (in utils.py)
All in-memory state lives in the `temp` class inside `utils.py`. It is **NOT** a separate `temp.py` module. Import it as:
```python
from utils import temp
```

Current state fields:
```python
temp.REFERRAL_CODES    # code(str) → user_id(int)
temp.REFERRAL_COUNTS   # user_id(int) → invite count(int)
temp.REFERRAL_BY       # new_user_id → referrer_id (prevents double-count)
temp.REFERRAL_REWARDED # set of user_ids already notified per milestone
temp.PREMIUM_USERS     # set of user_ids with premium (bypass verify)
temp.DAILY_VERIFY      # user_id → {date, count}
temp.VERIFY_STATS      # {daily, weekly, total}
temp.MOST_SEARCHED     # movie_name → count
temp.WEEKLY_SEARCHES   # week_key → {movie_name → count}
temp.U_NAME            # bot username (set at startup)
temp.B_NAME            # bot display name
```

**⚠️ Data resets on bot restart** — no persistent DB currently.

### `info.py` — all config
Key settings:
```python
ADMINS = [7801305224]              # from ADMINS env var
REFER_PREMIUM_THRESHOLD = 10       # invites needed for Premium (REFER_PREMIUM_THRESHOLD env var)
SHORTLINK_URL / SHORTLINK_API      # monetization API
SHORTLINK_URL2 / SHORTLINK_API2    # secondary
SHORTLINK_URL3 / SHORTLINK_API3    # tertiary
VERIFY_EXPIRE = 86400              # verify token TTL in seconds
```

### `commands.py` — start handler flow
The `/start` handler (around line 130) handles deep links. Order of checks:
1. FSub check
2. `verify_` token handler
3. `ref_` referral handler  ← **NEW** (around line 259)
4. `BATCH-` handler
5. File delivery (`file_`, `filep_`)

The `pm_text_redirect` filter (around line 470) whitelists commands that non-PM users can use. If you add a new command, add it to this list or it silently does nothing for group users.

---

## Features Built (Chronological)

### Session 1 — Core features + bugfixes
| Feature | Files Changed |
|---------|--------------|
| `/shortlink_stats` command | `utils.py` (VERIFY_STATS), `plugins/shortlink.py`, `plugins/commands.py` whitelist, `Script.py` help |
| Fix `/trending` not whitelisted | `plugins/commands.py` |
| Fix shortlink API missing `https://` | `plugins/shortlink.py` |
| Fix ADMINS env var empty | Set `ADMINS=7801305224` in Replit secrets |
| Rewrote `HELP_ADMIN_TXT` | `Script.py` |

### Session 2 — Referral System
| Feature | Files Changed |
|---------|--------------|
| `REFER_PREMIUM_THRESHOLD` config | `info.py` |
| Referral state in `temp` | `utils.py` |
| `get_refer_code()` | `utils.py` |
| `process_refer()` | `utils.py` |
| `get_refer_stats()` | `utils.py` |
| `get_refer_leaderboard()` | `utils.py` |
| `/refer` command (users) | `plugins/referral.py` (NEW) |
| `/refer_stats` command (admin) | `plugins/referral.py` (NEW) |
| `/set_refer_threshold` (admin) | `plugins/referral.py` (NEW) |
| `ref_CODE` deep link in `/start` | `plugins/commands.py` |
| Whitelist `refer`, `refer_stats`, `set_refer_threshold` | `plugins/commands.py` |
| `/refer` added to help text | `Script.py` |

---

## Referral System — Full Spec

### User flow
1. User sends `/refer`
2. Bot returns personal link: `https://t.me/BotUsername?start=ref_XXXXXXXX`
3. User shares link anywhere
4. New person clicks → starts bot → `ref_XXXXXXXX` deep link fires
5. `process_refer(new_user_id, code)` records invite:
   - Blocks self-referral
   - Blocks double-count (same person via multiple links)
6. Referrer gets a notification each invite
7. At exactly N invites (default 10): referrer auto-gets `temp.PREMIUM_USERS` + celebration message

### Helper functions (all in utils.py)
```python
get_refer_code(user_id: int) -> str
    # Returns or creates stable 8-char MD5-based code

process_refer(new_user_id: int, code: str) -> (referrer_id, milestone_hit)
    # Returns (None, False) for invalid/self/double
    # Returns (referrer_id, True) when count % THRESHOLD == 0

get_refer_stats(user_id: int) -> dict
    # {code, count, threshold, remaining, milestones}

get_refer_leaderboard(limit=10) -> list
    # [(user_id, count), ...] sorted descending
```

### Admin commands
- `/refer_stats` — leaderboard of top 15 referrers
- `/set_refer_threshold 5` — change goal (runtime only, resets on restart)

---

## Environment Variables / Secrets

| Variable | Value / Notes |
|----------|--------------|
| `BOT_TOKEN` | Telegram bot token |
| `API_ID` | Telegram API ID |
| `API_HASH` | Telegram API hash |
| `ADMINS` | `7801305224` |
| `SESSION_SECRET` | Session secret |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Used for API-based git pushes |
| `REFER_PREMIUM_THRESHOLD` | Optional, default `10` |

---

## Known Gotchas

1. **Two `/trending` lines in Script.py** — there are TWO occurrences (line 228 in `HELP_USER_TXT`, line 296 in another block). When editing, always provide extra surrounding lines as context to avoid wrong match.

2. **`temp` is a class, not a module** — it's defined inside `utils.py`. Never try to `import temp` as a module.

3. **No persistent DB** — all `temp.*` state resets when the bot restarts. If persistence is needed, write to a JSON file or add a DB.

4. **`pm_text_redirect` whitelist** — any new command must be added to the `filters.command([...])` list around line 470 of `commands.py`, or it won't work for users who message the bot in a non-PM context.

5. **GitHub path prefix** — the local path `tgbot/bot/X.py` maps to GitHub path `bot/X.py` (the repo's root is the `bot/` folder equivalent).

6. **Shortlink API format** — `https://DOMAIN/api?api=TOKEN&url=URL` — the `https://` must be in `SHORTLINK_URL` or prepended in code. Previous bug: URL was missing scheme.

---

## Commits History (recent)

| SHA | Description |
|-----|-------------|
| `34cc7db` | feat: /refer command system (referral.py + commands.py + utils.py + Script.py + info.py) |
| `ba31a3b` | fix: HELP_ADMIN_TXT rewrite |
| `f9e8d31` | fix: /trending whitelist |
| `b7f78f5` | fix: https:// in shortlink API URL |

---

## Next Possible Tasks (not yet built)

- **Persistent storage** — save `temp.PREMIUM_USERS`, `temp.REFERRAL_COUNTS`, etc. to JSON on disk so they survive restarts
- **Per-user referral expiry** — Premium lasts 30 days, not forever
- **Referral leaderboard in bot UI** — public `/leaderboard` command for users
- **Broadcast to all users** — admin sends message to everyone in DB
