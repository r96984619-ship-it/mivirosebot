import logging
from info import DATABASE_NAME, DATABASE_URI, IMDB, IMDB_TEMPLATE, MELCOW_NEW_USERS, P_TTI_SHOW_OFF, SINGLE_BUTTON, SPELL_CHECK_REPLY, PROTECT_CONTENT

logger = logging.getLogger(__name__)

USE_MONGO = bool(DATABASE_URI)

if USE_MONGO:
    try:
        import motor.motor_asyncio
        import certifi
        import pymongo
        # Sync ping to verify the connection is actually reachable before
        # committing to the async Motor client (Motor is lazy and only
        # raises on the first real query, which would crash every handler).
        _test = pymongo.MongoClient(
            DATABASE_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
        )
        _test.admin.command('ping')
        _test.close()
        del _test
    except Exception as e:
        logger.warning(f"MongoDB not reachable, using in-memory users/chats DB: {e}")
        USE_MONGO = False

if USE_MONGO:
    class Database:
        def __init__(self, uri, database_name):
            import certifi
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri, tlsCAFile=certifi.where())
            self.db = self._client[database_name]
            self.col = self.db.users
            self.grp = self.db.groups

        def new_user(self, id, name):
            return dict(id=id, name=name, ban_status=dict(is_banned=False, ban_reason=""))

        def new_group(self, id, title):
            return dict(id=id, title=title, chat_status=dict(is_disabled=False, reason=""))

        async def add_user(self, id, name):
            user = self.new_user(id, name)
            await self.col.insert_one(user)

        async def is_user_exist(self, id):
            user = await self.col.find_one({'id': int(id)})
            return bool(user)

        async def total_users_count(self):
            return await self.col.count_documents({})

        async def remove_ban(self, id):
            ban_status = dict(is_banned=False, ban_reason='')
            await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})

        async def ban_user(self, user_id, ban_reason="No Reason"):
            ban_status = dict(is_banned=True, ban_reason=ban_reason)
            await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

        async def get_ban_status(self, id):
            default = dict(is_banned=False, ban_reason='')
            user = await self.col.find_one({'id': int(id)})
            if not user:
                return default
            return user.get('ban_status', default)

        async def get_all_users(self):
            return self.col.find({})

        async def delete_user(self, user_id):
            await self.col.delete_many({'id': int(user_id)})

        async def get_banned(self):
            users = self.col.find({'ban_status.is_banned': True})
            chats = self.grp.find({'chat_status.is_disabled': True})
            b_chats = [chat['id'] async for chat in chats]
            b_users = [user['id'] async for user in users]
            return b_users, b_chats

        async def add_chat(self, chat, title):
            chat_doc = self.new_group(chat, title)
            await self.grp.insert_one(chat_doc)

        async def get_chat(self, chat):
            chat_doc = await self.grp.find_one({'id': int(chat)})
            return False if not chat_doc else chat_doc.get('chat_status')

        async def re_enable_chat(self, id):
            chat_status = dict(is_disabled=False, reason="")
            await self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})

        async def update_settings(self, id, settings):
            await self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})

        async def get_settings(self, id):
            default = {
                'button': SINGLE_BUTTON,
                'botpm': P_TTI_SHOW_OFF,
                'file_secure': PROTECT_CONTENT,
                'imdb': IMDB,
                'spell_check': SPELL_CHECK_REPLY,
                'welcome': MELCOW_NEW_USERS,
                'template': IMDB_TEMPLATE
            }
            chat = await self.grp.find_one({'id': int(id)})
            if chat:
                return chat.get('settings', default)
            return default

        async def disable_chat(self, chat, reason="No Reason"):
            chat_status = dict(is_disabled=True, reason=reason)
            await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})

        async def total_chat_count(self):
            return await self.grp.count_documents({})

        async def get_all_chats(self):
            return self.grp.find({})

        async def get_db_size(self):
            return (await self.db.command("dbstats"))['dataSize']

    db = Database(DATABASE_URI, DATABASE_NAME)

else:
    logger.info("Using in-memory mock users/chats database")

    class _MockAsyncIter:
        def __init__(self, items):
            self._items = iter(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._items)
            except StopIteration:
                raise StopAsyncIteration

    class Database:
        def __init__(self):
            self._users = {}   # id -> user dict
            self._groups = {}  # id -> group dict

        def new_user(self, id, name):
            return dict(id=id, name=name, ban_status=dict(is_banned=False, ban_reason=""))

        def new_group(self, id, title):
            return dict(id=id, title=title, chat_status=dict(is_disabled=False, reason=""))

        async def add_user(self, id, name):
            if id not in self._users:
                self._users[id] = self.new_user(id, name)

        async def is_user_exist(self, id):
            return int(id) in self._users

        async def total_users_count(self):
            return len(self._users)

        async def remove_ban(self, id):
            if id in self._users:
                self._users[id]['ban_status'] = dict(is_banned=False, ban_reason='')

        async def ban_user(self, user_id, ban_reason="No Reason"):
            if user_id in self._users:
                self._users[user_id]['ban_status'] = dict(is_banned=True, ban_reason=ban_reason)

        async def get_ban_status(self, id):
            default = dict(is_banned=False, ban_reason='')
            user = self._users.get(int(id))
            if not user:
                return default
            return user.get('ban_status', default)

        async def get_all_users(self):
            return _MockAsyncIter(list(self._users.values()))

        async def delete_user(self, user_id):
            self._users.pop(int(user_id), None)

        async def get_banned(self):
            b_users = [u['id'] for u in self._users.values() if u.get('ban_status', {}).get('is_banned')]
            b_chats = [c['id'] for c in self._groups.values() if c.get('chat_status', {}).get('is_disabled')]
            return b_users, b_chats

        async def add_chat(self, chat, title):
            if chat not in self._groups:
                self._groups[chat] = self.new_group(chat, title)

        async def get_chat(self, chat):
            group = self._groups.get(int(chat))
            return False if not group else group.get('chat_status')

        async def re_enable_chat(self, id):
            if id in self._groups:
                self._groups[id]['chat_status'] = dict(is_disabled=False, reason="")

        async def update_settings(self, id, settings):
            if id in self._groups:
                self._groups[id]['settings'] = settings

        async def get_settings(self, id):
            default = {
                'button': SINGLE_BUTTON,
                'botpm': P_TTI_SHOW_OFF,
                'file_secure': PROTECT_CONTENT,
                'imdb': IMDB,
                'spell_check': SPELL_CHECK_REPLY,
                'welcome': MELCOW_NEW_USERS,
                'template': IMDB_TEMPLATE
            }
            group = self._groups.get(int(id))
            if group:
                return group.get('settings', default)
            return default

        async def disable_chat(self, chat, reason="No Reason"):
            if chat in self._groups:
                self._groups[chat]['chat_status'] = dict(is_disabled=True, reason=reason)

        async def total_chat_count(self):
            return len(self._groups)

        async def get_all_chats(self):
            return _MockAsyncIter(list(self._groups.values()))

        async def get_db_size(self):
            return 0

    db = Database()
