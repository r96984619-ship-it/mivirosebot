import gc
import logging
import logging.config
import asyncio
import os
import time

logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.getLogger("cinemagoer").setLevel(logging.ERROR)

from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from pyrogram.sync import idle
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SESSION, API_ID, API_HASH, BOT_TOKEN, LOG_STR
from utils import temp
from persistence import load_state, save_state, auto_save_loop
from typing import Union, Optional, AsyncGenerator
from pyrogram import types

logger = logging.getLogger(__name__)

# ── Health-check server (starts once, survives reconnects) ────────────────────

async def _health_server():
    """Tiny HTTP server on $PORT for Render / cloud health checks."""
    from aiohttp import web
    port = int(os.environ.get("PORT", 8080))

    async def handle(_request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check server running on port {port}.")


# ── Bot client ────────────────────────────────────────────────────────────────

class Bot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )

    async def start(self):
        # Load persisted state FIRST so premium/referral data is ready
        load_state()
        try:
            b_users, b_chats = await db.get_banned()
            temp.BANNED_USERS = b_users
            temp.BANNED_CHATS = b_chats
        except Exception as e:
            logger.warning(f"MongoDB not reachable, running with in-memory DB: {e}")
            temp.BANNED_USERS = []
            temp.BANNED_CHATS = []
        await super().start()
        try:
            await Media.ensure_indexes()
        except Exception as e:
            logger.warning(f"MongoDB index creation skipped: {e}")
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        temp.BOT_START_TIME = time.time()
        self.username = '@' + me.username
        logger.info(
            f"{me.first_name} with Pyrogram v{__version__} (Layer {layer}) "
            f"started on {me.username}."
        )
        logger.info(LOG_STR)

    async def stop(self, *args):
        await save_state()          # persist before exit
        await super().stop()
        logger.info("Bot stopped.")

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat's history sequentially."""
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(
                chat_id, list(range(current, current + new_diff + 1))
            )
            for message in messages:
                yield message
                current += 1


# ── Auto-reconnect supervisor loop ───────────────────────────────────────────

_INITIAL_DELAY = 5     # seconds before first retry
_MAX_DELAY     = 120   # cap at 2 minutes


async def main():
    # Health server + auto-save loop start once and stay up across all reconnects.
    loop = asyncio.get_running_loop()
    loop.create_task(_health_server())
    loop.create_task(auto_save_loop())
    await asyncio.sleep(1)  # yield so health server binds to port first

    delay = _INITIAL_DELAY
    attempt = 0

    while True:
        app = Bot()
        started = False  # track whether start() succeeded so we know if stop() is safe

        try:
            attempt += 1
            if attempt > 1:
                logger.info(f"Reconnect attempt #{attempt} ...")
            await app.start()
            started = True          # from here on, stop() is safe to call
            delay = _INITIAL_DELAY  # reset backoff on successful connect
            attempt = 0
            await idle()            # blocks until SIGTERM / SIGINT

            # idle() returned cleanly (SIGTERM) — graceful shutdown
            logger.info("Shutdown signal received — stopping bot.")
            try:
                await app.stop()
            except Exception:
                pass
            break  # exit the reconnect loop

        except (KeyboardInterrupt, SystemExit):
            logger.info("Keyboard interrupt — stopping bot.")
            if started:
                try:
                    await app.stop()
                except Exception:
                    pass
            break

        except asyncio.CancelledError:
            logger.info("Event loop cancelled — stopping bot.")
            if started:
                try:
                    await app.stop()
                except Exception:
                    pass
            break

        except Exception as exc:
            logger.warning(
                f"Bot disconnected ({exc.__class__.__name__}: {exc}). "
                f"Reconnecting in {delay}s ..."
            )
            # Only stop() if start() had succeeded; if start() itself threw,
            # calling stop() on the half-initialised client can leave the
            # session SQLite file locked for the next attempt.
            if started:
                try:
                    await app.stop()
                except Exception:
                    pass

        # Discard the old instance and force GC so the previous Pyrogram
        # session file / SQLite connection is released before we open it again.
        del app
        gc.collect()

        await asyncio.sleep(delay)
        delay = min(delay * 2, _MAX_DELAY)


if __name__ == "__main__":
    asyncio.run(main())
