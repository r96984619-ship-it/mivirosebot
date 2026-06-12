# 🎬 Miviesfather — Telegram Movie Filter Bot

A fully-featured Telegram bot that indexes media files from channels, serves them via search/inline queries, shows IMDb info, enforces force-subscribe, supports shortlink monetization, premium users, and bulk movie announcements.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🔍 Movie search | Type a movie name in any connected group — bot replies with file buttons |
| 🎭 IMDb lookup | Poster, plot, genre, cast, rating, runtime auto-fetched |
| 📡 Inline search | `@yourbot movie name` works anywhere |
| 🔒 Force Subscribe | Gate access behind up to **3 channels** |
| 💰 Shortlink verify | Daily verification via up to **3 shortlink providers** |
| 👑 Premium users | Bypass verification, direct file access |
| 📢 `/announce` | Broadcast movie poster + IMDb info + Search button to all users |
| 📊 `/stats` | Live DB + server stats dashboard |
| 📚 Multi-page `/help` | Admin / Filter / User sections with navigation |
| 🔄 Auto-reconnect | Exponential-backoff reconnect loop — never stays down |
| 🗄️ MongoDB | Persistent storage; falls back to in-memory if unavailable |
| 🐳 Docker-ready | Single `docker run` command to deploy anywhere |

---

## 🚀 One-Click Deploy

Pick any platform below — all are free tiers:

| Platform | Speed | Persistent Storage | Free Tier |
|----------|-------|--------------------|-----------|
| [Replit](#-replit-recommended-for-beginners) | ⚡ Fastest setup | ✅ via Replit DB | ✅ |
| [Railway](#-railway) | Fast | ✅ volumes | ✅ 5 USD/mo credit |
| [Render](#-render) | Medium | ✅ disks | ✅ 750 hrs/mo |
| [Heroku](#-heroku) | Medium | ✅ add-ons | ✅ Eco dynos |
| [Fly.io](#-flyio) | Fast | ✅ volumes | ✅ 3 shared VMs |
| [Docker / VPS](#-docker--vps-self-hosted) | Manual | ✅ bind mounts | Your server |
| [Koyeb](#-koyeb) | Fast | ✅ | ✅ nano instance |

---

## 📋 Required Secrets

You need these **3 secrets** on every platform:

| Variable | Where to get it |
|----------|----------------|
| `API_ID` | [my.telegram.org](https://my.telegram.org) → API Development Tools |
| `API_HASH` | Same page as API_ID |
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` |

See the [full environment variables table](#-all-environment-variables) below.

---

## ☁️ Platform Guides

### 🟣 Replit (Recommended for beginners)

[![Deploy on Replit](https://replit.com/badge/github/r96984619-ship-it/Mediafilterbot)](https://replit.com/new/github/r96984619-ship-it/Mediafilterbot)

1. Click the button above — Replit forks the repo and opens the Agent
2. Tell the Agent: *"Set up this Telegram bot. I'll provide the secrets."*
3. Add your 3 secrets in the **Secrets** tab (🔒 icon in the sidebar)
4. Click **Run** — the bot starts immediately

---

### 🚂 Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/ZweBXA?referralCode=Mediafilterbot)

1. Click the button above (or go to [railway.app](https://railway.app) → New Project → Deploy from GitHub)
2. Connect your GitHub account and select this repo
3. Go to **Variables** and add your secrets
4. Railway reads `railway.json` automatically — click **Deploy**
5. Check **Logs** to confirm the bot is running

> ℹ️ Railway needs a `PORT` — the bot's health server already reads `$PORT`.

---

### 🟦 Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/r96984619-ship-it/Mediafilterbot)

1. Click the button above
2. Render reads `render.yaml` and creates a **Background Worker** service
3. Fill in your secrets in the Environment Variables section
4. Click **Apply** — Render builds and deploys automatically

> ℹ️ Choose **Background Worker** (not Web Service) — Telegram bots don't need HTTP ports.

---

### 🟪 Heroku

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/r96984619-ship-it/Mediafilterbot)

1. Click the button above (requires a free Heroku account)
2. Fill in all environment variables in the form shown
3. Click **Deploy app** — Heroku reads `Procfile` and `app.json`
4. Go to **Resources** and make sure the `worker` dyno is ON (toggle it)

> ⚠️ Heroku free dynos sleep after 30 min of inactivity — upgrade to Eco ($5/mo) for 24/7.

---

### 🪁 Fly.io

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Login
fly auth login

# 3. Clone the repo
git clone https://github.com/r96984619-ship-it/Mediafilterbot.git
cd Mediafilterbot

# 4. Create the app (fly.toml is already included)
fly launch --no-deploy

# 5. Set your secrets
fly secrets set API_ID=your_api_id
fly secrets set API_HASH=your_api_hash
fly secrets set BOT_TOKEN=your_bot_token
fly secrets set DATABASE_URI=your_mongodb_uri   # optional

# 6. Deploy
fly deploy
```

> ℹ️ Fly.io gives 3 free shared-CPU VMs. The included `fly.toml` sets `min_machines_running=1` so the bot never sleeps.

---

### 🐳 Docker / VPS (Self-Hosted)

The easiest way to run on any Linux server (Ubuntu, Debian, etc.):

#### Quick start (one command)

```bash
docker run -d --name miviesfather-bot --restart unless-stopped \
  -e API_ID=your_api_id \
  -e API_HASH=your_api_hash \
  -e BOT_TOKEN=your_bot_token \
  -e DATABASE_URI=your_mongodb_uri \
  ghcr.io/r96984619-ship-it/mediafilterbot:latest
```

#### Build from source

```bash
git clone https://github.com/r96984619-ship-it/Mediafilterbot.git
cd Mediafilterbot

# Copy and fill in your secrets
cp .env.example .env
nano .env          # edit with your values

# Build + start
docker compose up -d

# View logs
docker compose logs -f bot
```

#### Manual (no Docker)

```bash
git clone https://github.com/r96984619-ship-it/Mediafilterbot.git
cd Mediafilterbot

cp .env.example .env
nano .env          # fill in your secrets

bash bot/start.sh
```

To keep it running with systemd:

```bash
# /etc/systemd/system/miviesfather.service
[Unit]
Description=Miviesfather Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Mediafilterbot
ExecStart=/bin/bash bot/start.sh
EnvironmentFile=/home/ubuntu/Mediafilterbot/.env
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable miviesfather
sudo systemctl start miviesfather
sudo journalctl -u miviesfather -f   # view logs
```

---

### 🟨 Koyeb

1. Go to [app.koyeb.com](https://app.koyeb.com) → **Create App**
2. Select **GitHub** → choose this repo
3. Set **Builder** to **Dockerfile** (uses the included `Dockerfile`)
4. Add environment variables (API_ID, API_HASH, BOT_TOKEN, DATABASE_URI)
5. Set **Port** to `8080` — the health server responds on `/health`
6. Click **Deploy**

> ℹ️ Koyeb's free nano instance (0.1 vCPU / 256 MB RAM) is sufficient for this bot.

---

## 🗄️ MongoDB Setup (Recommended)

Without `DATABASE_URI` the bot works fine but **data resets on every restart**.

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com) → create a free M0 cluster
2. **Database Access** → Add User → Password authentication
3. **Network Access** → Add IP → **Allow Access from Anywhere** (`0.0.0.0/0`)
4. **Connect** → Drivers → copy the URI
5. Replace `<password>` and set as `DATABASE_URI` environment variable

---

## 🔑 All Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `API_ID` | Telegram API ID | `12345678` |
| `API_HASH` | Telegram API Hash | `abcdef1234` |
| `BOT_TOKEN` | Bot token from @BotFather | `123456:ABC` |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URI` | *(none)* | MongoDB URI — uses in-memory if unset |
| `DATABASE_NAME` | `Rajappan` | MongoDB database name |

### Access Control

| Variable | Description |
|----------|-------------|
| `ADMINS` | Space-separated admin user IDs |
| `CHANNELS` | Channel IDs to auto-index (space-separated) |
| `LOG_CHANNEL` | Log channel ID (0 = off) |
| `AUTH_CHANNEL` | Force-subscribe channel #1 |
| `FSUB_2` | Force-subscribe channel #2 |
| `FSUB_3` | Force-subscribe channel #3 |
| `INDEX_REQ_CHANNEL` | Channel where indexing is requested |
| `FILE_STORE_CHANNEL` | Channel for /genlink file storage |

### Shortlink Monetization

| Variable | Description |
|----------|-------------|
| `SHORTLINK_URL` | API domain (e.g. `api.shareus.io`) |
| `SHORTLINK_API` | API key for provider 1 |
| `SHORTLINK_URL2` / `SHORTLINK_API2` | Provider 2 |
| `SHORTLINK_URL3` / `SHORTLINK_API3` | Provider 3 |
| `VERIFY_DAILY_LIMIT` | Verifications needed per day (default: `1`) |
| `VERIFY_EXPIRE` | Seconds until verification expires (default: `86400`) |
| `VERIFY_TUTORIAL` | Tutorial URL for provider 1 |
| `VERIFY_TUTORIAL2` / `VERIFY_TUTORIAL3` | Tutorial URLs 2 & 3 |

### Premium / Group

| Variable | Description |
|----------|-------------|
| `SUB_LINK` | Link to buy premium subscription |
| `PREMIUM_PASS` | Secret passphrase for self-activating premium |
| `MOVIE_GROUP` | Your movie group link |
| `SUPPORT_CHAT` | Support username (default: `BackupChannel5211`) |

### Feature Toggles

| Variable | Default | Description |
|----------|---------|-------------|
| `IMDB` | `True` | Show IMDb info |
| `SINGLE_BUTTON` | `False` | One button per file instead of two |
| `PROTECT_CONTENT` | `False` | Prevent file forwarding |
| `SPELL_CHECK_REPLY` | `True` | Suggest corrections when no results |
| `P_TTI_SHOW_OFF` | `False` | Redirect group users to PM |
| `LONG_IMDB_DESCRIPTION` | `False` | Full IMDb plot |
| `MELCOW_NEW_USERS` | `True` | Welcome message for new group members |
| `PUBLIC_FILE_STORE` | `True` | Allow public access to stored files |

---

## 📁 Project Structure

```
bot/
├── bot.py              ← Entry point — auto-reconnect supervisor loop
├── info.py             ← All config loaded from environment variables
├── utils.py            ← Shared helpers: IMDb, shortlink, verify, caption clean
├── Script.py           ← All message templates (edit here to change bot text)
├── requirements.txt    ← Python dependencies
├── start.sh            ← Startup script (installs deps, then runs bot)
├── database/
│   ├── ia_filterdb.py          ← Media index (files from channels)
│   ├── users_chats_db.py       ← Users & groups database
│   ├── connections_mdb.py      ← Group↔PM connections
│   └── filters_mdb.py          ← Manual keyword filters
└── plugins/
    ├── commands.py     ← /start /help /stats /settings /premium
    ├── pm_filter.py    ← Auto-filter, file buttons, shortlink gate, callbacks
    ├── filters.py      ← /filter /filters /del /delall
    ├── broadcast.py    ← /broadcast /announce /grp_broadcast
    ├── misc.py         ← /id /info /imdb /search
    ├── inline.py       ← Inline query handler
    ├── index.py        ← Channel indexing
    ├── connection.py   ← /connect /disconnect /connections
    ├── genlink.py      ← /genlink /batch
    ├── banned.py       ← Banned user/chat filter
    ├── channel.py      ← Auto-index new media from channels
    └── p_ttishow.py    ← Group join/leave/ban/stats and welcome

Deployment files (root):
├── Dockerfile          ← Universal container (Fly.io, Koyeb, VPS)
├── docker-compose.yml  ← Local testing
├── Procfile            ← Heroku worker dyno
├── app.json            ← Heroku one-click deploy config
├── railway.json        ← Railway deploy config
├── render.yaml         ← Render deploy config
├── fly.toml            ← Fly.io config
└── .env.example        ← Template for all environment variables
```

---

## 📋 Admin Commands Reference

| Command | Description |
|---------|-------------|
| `/stats` | Database + server statistics |
| `/broadcast` | Send a message to all users (reply to any message) |
| `/announce <movie>` | Fetch IMDb poster + broadcast with Search button |
| `/grp_broadcast` | Send a message to all groups |
| `/fsu` `/fsu2` `/fsu3` | Set force-subscribe channels |
| `/del_fsub` `/del_fsub2` `/del_fsub3` | Remove force-subscribe channels |
| `/show_fsub` | Show current force-subscribe config |
| `/shortlink` | Set shortlink provider 1 |
| `/shortlink2` `/shortlink3` | Set providers 2 and 3 |
| `/shortlink_status` | Show current shortlink config |
| `/tutorial` `/tutorial2` `/tutorial3` | Set tutorial URLs |
| `/set_daily_verify <n>` | Set verifications needed per day |
| `/premium <user_id>` | Grant premium to a user |
| `/unpremium <user_id>` | Revoke premium |
| `/list_premium` | List all premium users |
| `/set_sub_link <url>` | Set premium purchase link |
| `/set_movie_group <url>` | Set movie group link |
| `/ban` `/unban` | Ban / unban users |
| `/users` `/chats` | Count users / groups in DB |
| `/logs` | Get the bot log file |
| `/leave <chat_id>` | Make the bot leave a group |
| `/delete` | Delete a file from the index (reply to file) |
| `/deleteall` | Delete all indexed files |
| `/setskip <n>` | Skip first N messages when indexing |
| `/genlink` | Generate a start link for a stored file |
| `/batch <ch> <from> <to>` | Generate a batch link for a range of messages |

---

## ⚙️ How Auto-Reconnect Works

The bot uses a supervisor loop with **exponential backoff**:

```
Connection drop → wait 5s → reconnect
Fails again     → wait 10s → reconnect
Fails again     → wait 20s → ...
                             (caps at 2 minutes)
Reconnects OK   → reset back to 5s delay
```

The health check server (used by Railway, Render, Fly.io, Koyeb) stays running the entire time — the platform never marks the service as down during a reconnect cycle.

---

## 🤖 Extending With an AI Agent

This repo is designed to be **agent-friendly**. Use these prompts with Replit Agent, Cursor, or any AI assistant:

> *"Add a `/trending` command that shows the 10 most-searched movies this week."*

> *"Add a 4th shortlink provider using SHORTLINK_URL4 and SHORTLINK_API4."*

> *"Make the bot check force-subscribe only for new users, not on every file request."*

> *"Add a `/schedule` command to broadcast a movie announcement at a specific time."*

---

## 📄 License

MIT — fork freely, build your own bot, credit appreciated but not required.
