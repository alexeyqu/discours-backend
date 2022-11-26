import json
import uuid
from datetime import datetime, timezone

from auth.authenticate import login_required
from base.redis import redis
from base.resolvers import mutation


@mutation.field("updateChat")
@login_required
async def update_chat(_, info, chat_new: dict):
    """
    updating chat
    requires info["request"].user.slug to be in chat["admins"]

    :param info: GraphQLInfo with request
    :param chat_new: dict with chat data
    :return: Result { error chat }
    """
    user = info.context["request"].user
    chat_id = chat_new["id"]
    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {
            "error": "chat not exist"
        }
    chat = dict(json.loads(chat))
    if user.slug in chat["admins"]:
        chat.update({
            "title": chat_new.get("title", chat["title"]),
            "description": chat_new.get("description", chat["description"]),
            "updatedAt": int(datetime.now(tz=timezone.utc).timestamp()),
            "admins": chat_new.get("admins", chat["admins"]),
            "users": chat_new.get("users", chat["users"])
        })
    await redis.execute("SET", f"chats/{chat.id}", json.dumps(chat))
    await redis.execute("COMMIT")

    return {
        "error": None,
        "chat": chat
    }


@mutation.field("createChat")
@login_required
async def create_chat(_, info, title="", members=[]):
    user = info.context["request"].user
    chat = {}
    if user.slug not in members:
        members.append(user.slug)

    # reuse chat craeted before if exists
    if len(members) == 2 and title == "":
        chats1 = await redis.execute("SMEMBERS", f"chats_by_user/{members[0].slug}")
        chats2 = await redis.execute("SMEMBERS", f"chats_by_user/{members[1].slug}")
        chat = None
        for c in chats1.intersection(chats2):
            chat = await redis.execute("GET", f"chats/{c.decode('utf-8')}")
            if chat:
                chat = json.loads(chat)
                if chat.title == "":
                    break
        if chat:
            return {
                "chat": chat,
                "error": "existed"
            }

    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "users": members,
        "title": title,
        "createdBy": user.slug,
        "createdAt": int(datetime.now(tz=timezone.utc).timestamp()),
        "updatedAt": int(datetime.now(tz=timezone.utc).timestamp()),
        # "admins": [user.slug, ]
    }

    for m in members:
        await redis.execute("SADD", f"chats_by_user/{m}", chat_id)
    await redis.execute("SET", f"chats/{chat_id}", json.dumps(chat))
    await redis.execute("SET", f"chats/{chat_id}/next_message_id", str(0))
    await redis.execute("COMMIT")
    return {
        "error": None,
        "chat": chat
    }


@mutation.field("deleteChat")
@login_required
async def delete_chat(_, info, chat_id: str):
    user = info.context["request"].user
    chat = await redis.execute("GET", f"/chats/{chat_id}")
    if chat:
        chat = dict(json.loads(chat))
        if user.slug in chat['admins']:
            await redis.execute("DEL", f"chats/{chat_id}")
            await redis.execute("SREM", "chats_by_user/" + user, chat_id)
            await redis.execute("COMMIT")
    else:
        return {
            "error": "chat not exist"
        }
