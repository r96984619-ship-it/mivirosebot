import logging
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

USE_MONGO = bool(DATABASE_URI)

if USE_MONGO:
    try:
        import pymongo
        import certifi
        myclient = pymongo.MongoClient(DATABASE_URI, tlsCAFile=certifi.where())
        mydb = myclient[DATABASE_NAME]
        mycol = mydb['CONNECTION']
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e}. Using in-memory connections.")
        USE_MONGO = False

if not USE_MONGO:
    # In-memory connections store: user_id -> {group_details: [{group_id}], active_group: id}
    _CONNECTIONS = {}

    async def add_connection(group_id, user_id):
        user = _CONNECTIONS.get(user_id)
        if user is not None:
            existing = [x['group_id'] for x in user['group_details']]
            if group_id in existing:
                return False
            user['group_details'].append({'group_id': group_id})
            user['active_group'] = group_id
            return True
        _CONNECTIONS[user_id] = {
            'group_details': [{'group_id': group_id}],
            'active_group': group_id,
        }
        return True

    async def active_connection(user_id):
        user = _CONNECTIONS.get(user_id)
        if not user:
            return None
        gid = user.get('active_group')
        return int(gid) if gid is not None else None

    async def all_connections(user_id):
        user = _CONNECTIONS.get(user_id)
        if user is None:
            return None
        return [x['group_id'] for x in user['group_details']]

    async def if_active(user_id, group_id):
        user = _CONNECTIONS.get(user_id)
        return user is not None and user.get('active_group') == group_id

    async def make_active(user_id, group_id):
        user = _CONNECTIONS.get(user_id)
        if user is None:
            return False
        user['active_group'] = group_id
        return True

    async def make_inactive(user_id):
        user = _CONNECTIONS.get(user_id)
        if user is None:
            return False
        user['active_group'] = None
        return True

    async def delete_connection(user_id, group_id):
        user = _CONNECTIONS.get(user_id)
        if not user:
            return False
        before = len(user['group_details'])
        user['group_details'] = [x for x in user['group_details'] if x['group_id'] != group_id]
        if len(user['group_details']) == before:
            return False
        if user.get('active_group') == group_id:
            if user['group_details']:
                user['active_group'] = user['group_details'][-1]['group_id']
            else:
                user['active_group'] = None
        return True

else:
    async def add_connection(group_id, user_id):
        query = mycol.find_one({"_id": user_id}, {"_id": 0, "active_group": 0})
        if query is not None:
            group_ids = [x["group_id"] for x in query["group_details"]]
            if group_id in group_ids:
                return False
        group_details = {"group_id": group_id}
        data = {'_id': user_id, 'group_details': [group_details], 'active_group': group_id}
        if mycol.count_documents({"_id": user_id}) == 0:
            try:
                mycol.insert_one(data)
                return True
            except Exception:
                logger.exception('Some error occurred!', exc_info=True)
        else:
            try:
                mycol.update_one(
                    {'_id': user_id},
                    {"$push": {"group_details": group_details}, "$set": {"active_group": group_id}}
                )
                return True
            except Exception:
                logger.exception('Some error occurred!', exc_info=True)

    async def active_connection(user_id):
        query = mycol.find_one({"_id": user_id}, {"_id": 0, "group_details": 0})
        if not query:
            return None
        group_id = query['active_group']
        return int(group_id) if group_id is not None else None

    async def all_connections(user_id):
        query = mycol.find_one({"_id": user_id}, {"_id": 0, "active_group": 0})
        if query is not None:
            return [x["group_id"] for x in query["group_details"]]
        return None

    async def if_active(user_id, group_id):
        query = mycol.find_one({"_id": user_id}, {"_id": 0, "group_details": 0})
        return query is not None and query['active_group'] == group_id

    async def make_active(user_id, group_id):
        update = mycol.update_one({'_id': user_id}, {"$set": {"active_group": group_id}})
        return update.modified_count != 0

    async def make_inactive(user_id):
        update = mycol.update_one({'_id': user_id}, {"$set": {"active_group": None}})
        return update.modified_count != 0

    async def delete_connection(user_id, group_id):
        try:
            update = mycol.update_one(
                {"_id": user_id},
                {"$pull": {"group_details": {"group_id": group_id}}}
            )
            if update.modified_count == 0:
                return False
            query = mycol.find_one({"_id": user_id}, {"_id": 0})
            if len(query["group_details"]) >= 1:
                if query['active_group'] == group_id:
                    prvs_group_id = query["group_details"][-1]["group_id"]
                    mycol.update_one({'_id': user_id}, {"$set": {"active_group": prvs_group_id}})
            else:
                mycol.update_one({'_id': user_id}, {"$set": {"active_group": None}})
            return True
        except Exception as e:
            logger.exception(f'Some error occurred! {e}', exc_info=True)
            return False
