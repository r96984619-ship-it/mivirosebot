import logging
import re
import base64
from struct import pack
from info import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

USE_MONGO = bool(DATABASE_URI)

if USE_MONGO:
    try:
        from pyrogram.file_id import FileId
        from pymongo.errors import DuplicateKeyError
        from umongo import Instance, Document, fields
        from motor.motor_asyncio import AsyncIOMotorClient
        from marshmallow.exceptions import ValidationError

        import certifi
        client = AsyncIOMotorClient(DATABASE_URI, tlsCAFile=certifi.where())
        db = client[DATABASE_NAME]
        instance = Instance.from_db(db)

        @instance.register
        class Media(Document):
            file_id = fields.StrField(attribute='_id')
            file_ref = fields.StrField(allow_none=True)
            file_name = fields.StrField(required=True)
            file_size = fields.IntField(required=True)
            file_type = fields.StrField(allow_none=True)
            mime_type = fields.StrField(allow_none=True)
            caption = fields.StrField(allow_none=True)

            class Meta:
                indexes = ('$file_name', )
                collection_name = COLLECTION_NAME

    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}. Falling back to in-memory DB.")
        USE_MONGO = False

if not USE_MONGO:
    # In-memory mock database
    logger.info("Using in-memory mock database (no DATABASE_URI configured)")

    class _MockCursor:
        def __init__(self, items):
            self._items = list(items)
            self._sort_key = None
            self._sort_dir = 1
            self._skip_n = 0
            self._limit_n = None

        def sort(self, key, direction):
            self._sort_key = key
            self._sort_dir = direction
            return self

        def skip(self, n):
            self._skip_n = n
            return self

        def limit(self, n):
            self._limit_n = n
            return self

        async def to_list(self, length=None):
            items = self._items
            if self._sort_key == '$natural':
                items = list(reversed(items))
            items = items[self._skip_n:]
            if self._limit_n:
                items = items[:self._limit_n]
            if length:
                items = items[:length]
            return [_MockMediaDoc(**item) for item in items]

    class _MockCollection:
        def __init__(self, store):
            self._store = store

        async def delete_one(self, filter_dict):
            for i, doc in enumerate(self._store):
                if all(doc.get(k) == v for k, v in filter_dict.items()):
                    del self._store[i]
                    return type('R', (), {'deleted_count': 1})()
            return type('R', (), {'deleted_count': 0})()

        async def delete_many(self, filter_dict):
            before = len(self._store)
            self._store[:] = [
                doc for doc in self._store
                if not all(doc.get(k) == v for k, v in filter_dict.items())
            ]
            return type('R', (), {'deleted_count': before - len(self._store)})()

        async def drop(self):
            self._store.clear()

    _MEDIA_STORE = []

    class _MockMediaDoc:
        def __init__(self, file_id=None, file_ref=None, file_name=None,
                     file_size=0, file_type=None, mime_type=None, caption=None, **kw):
            self.file_id = file_id
            self.file_ref = file_ref
            self.file_name = file_name
            self.file_size = file_size
            self.file_type = file_type
            self.mime_type = mime_type
            self.caption = caption

        def to_dict(self):
            return {
                'file_id': self.file_id,
                'file_ref': self.file_ref,
                'file_name': self.file_name,
                'file_size': self.file_size,
                'file_type': self.file_type,
                'mime_type': self.mime_type,
                'caption': self.caption,
            }

        async def commit(self):
            # Check for duplicates
            for doc in _MEDIA_STORE:
                if doc.get('file_id') == self.file_id:
                    from pymongo.errors import DuplicateKeyError
                    raise DuplicateKeyError("duplicate key error")
            _MEDIA_STORE.append(self.to_dict())

    class Media:
        collection = _MockCollection(_MEDIA_STORE)

        @classmethod
        async def ensure_indexes(cls):
            pass

        @classmethod
        async def count_documents(cls, filter_dict=None):
            if not filter_dict:
                return len(_MEDIA_STORE)
            return sum(1 for doc in _MEDIA_STORE if _matches(doc, filter_dict))

        @classmethod
        def find(cls, filter_dict=None):
            if not filter_dict:
                return _MockCursor(_MEDIA_STORE)
            return _MockCursor([doc for doc in _MEDIA_STORE if _matches(doc, filter_dict)])

    def _matches(doc, filter_dict):
        for key, val in filter_dict.items():
            if key == '$or':
                if not any(_matches(doc, sub) for sub in val):
                    return False
            elif hasattr(val, 'pattern'):  # regex
                field_val = doc.get(key) or ''
                if not val.search(str(field_val)):
                    return False
            else:
                if doc.get(key) != val:
                    return False
        return True

    # Stub DuplicateKeyError for in-memory path
    try:
        from pymongo.errors import DuplicateKeyError
    except ImportError:
        class DuplicateKeyError(Exception):
            pass

    ValidationError = ValueError

    def unpack_new_file_id(new_file_id):
        """Return file_id, file_ref — stub for mock mode"""
        return new_file_id, ""

    def encode_file_id(s: bytes) -> str:
        r = b""
        n = 0
        for i in s + bytes([22]) + bytes([4]):
            if i == 0:
                n += 1
            else:
                if n:
                    r += b"\x00" + bytes([n])
                    n = 0
                r += bytes([i])
        return base64.urlsafe_b64encode(r).decode().rstrip("=")

    def encode_file_ref(file_ref: bytes) -> str:
        return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

    async def save_file(media):
        file_id = getattr(media, 'file_id', None)
        if not file_id:
            return False, 2
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(getattr(media, 'file_name', '') or ''))
        try:
            caption_val = None
            cap = getattr(media, 'caption', None)
            if cap:
                caption_val = cap.html if hasattr(cap, 'html') else str(cap)
            doc = _MockMediaDoc(
                file_id=file_id,
                file_ref="",
                file_name=file_name,
                file_size=getattr(media, 'file_size', 0),
                file_type=getattr(media, 'file_type', None),
                mime_type=getattr(media, 'mime_type', None),
                caption=caption_val,
            )
            await doc.commit()
            logger.info(f'{file_name} saved to in-memory database')
            return True, 1
        except DuplicateKeyError:
            logger.warning(f'{getattr(media, "file_name", "NO_FILE")} is already saved in database')
            return False, 0
        except Exception:
            logger.exception('Error saving file')
            return False, 2

    async def get_search_results(query, file_type=None, max_results=10, offset=0, filter=False):
        query = query.strip()
        if not query:
            raw_pattern = '.'
        elif ' ' not in query:
            raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
        else:
            raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')
        try:
            regex = re.compile(raw_pattern, flags=re.IGNORECASE)
        except Exception:
            return [], 0, 0

        if USE_CAPTION_FILTER:
            filter_dict = {'$or': [{'file_name': regex}, {'caption': regex}]}
        else:
            filter_dict = {'file_name': regex}

        if file_type:
            filter_dict['file_type'] = file_type

        total_results = await Media.count_documents(filter_dict)
        next_offset = offset + max_results
        if next_offset > total_results:
            next_offset = ''

        cursor = Media.find(filter_dict)
        cursor.sort('$natural', -1)
        cursor.skip(offset).limit(max_results)
        files = await cursor.to_list(length=max_results)
        return files, next_offset, total_results

    async def get_file_details(query):
        for doc in _MEDIA_STORE:
            if doc.get('file_id') == query:
                return [_MockMediaDoc(**doc)]
        return []

else:
    # Real MongoDB implementations
    from pyrogram.file_id import FileId
    from pymongo.errors import DuplicateKeyError
    from marshmallow.exceptions import ValidationError

    def encode_file_id(s: bytes) -> str:
        r = b""
        n = 0
        for i in s + bytes([22]) + bytes([4]):
            if i == 0:
                n += 1
            else:
                if n:
                    r += b"\x00" + bytes([n])
                    n = 0
                r += bytes([i])
        return base64.urlsafe_b64encode(r).decode().rstrip("=")

    def encode_file_ref(file_ref: bytes) -> str:
        return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

    def unpack_new_file_id(new_file_id):
        """Return file_id, file_ref"""
        decoded = FileId.decode(new_file_id)
        file_id = encode_file_id(
            pack(
                "<iiqq",
                int(decoded.file_type),
                decoded.dc_id,
                decoded.media_id,
                decoded.access_hash
            )
        )
        file_ref = encode_file_ref(decoded.file_reference)
        return file_id, file_ref

    async def save_file(media):
        """Save file in database"""
        file_id, file_ref = unpack_new_file_id(media.file_id)
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        try:
            file = Media(
                file_id=file_id,
                file_ref=file_ref,
                file_name=file_name,
                file_size=media.file_size,
                file_type=media.file_type,
                mime_type=media.mime_type,
                caption=media.caption.html if media.caption else None,
            )
        except ValidationError:
            logger.exception('Error occurred while saving file in database')
            return False, 2
        else:
            try:
                await file.commit()
            except DuplicateKeyError:
                logger.warning(f'{getattr(media, "file_name", "NO_FILE")} is already saved in database')
                return False, 0
            else:
                logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to database')
                return True, 1

    async def get_search_results(query, file_type=None, max_results=10, offset=0, filter=False):
        """For given query return (results, next_offset)"""
        query = query.strip()
        if not query:
            raw_pattern = '.'
        elif ' ' not in query:
            raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
        else:
            raw_pattern = query.replace(' ', r'.*[\s\.\+\-_]')

        try:
            regex = re.compile(raw_pattern, flags=re.IGNORECASE)
        except Exception:
            return []

        if USE_CAPTION_FILTER:
            filter_q = {'$or': [{'file_name': regex}, {'caption': regex}]}
        else:
            filter_q = {'file_name': regex}

        if file_type:
            filter_q['file_type'] = file_type

        total_results = await Media.count_documents(filter_q)
        next_offset = offset + max_results
        if next_offset > total_results:
            next_offset = ''

        cursor = Media.find(filter_q)
        cursor.sort('$natural', -1)
        cursor.skip(offset).limit(max_results)
        files = await cursor.to_list(length=max_results)
        return files, next_offset, total_results

    async def get_file_details(query):
        filter_q = {'file_id': query}
        cursor = Media.find(filter_q)
        filedetails = await cursor.to_list(length=1)
        return filedetails
