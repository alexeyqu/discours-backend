import asyncio
import json
from typing import Any
from datetime import datetime, timezone
from graphql.type import GraphQLResolveInfo
from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.redis import redis
from base.resolvers import mutation, subscription
from services.following import FollowingManager, FollowingResult, Following
from validations.inbox import Message


@mutation.field("createMessage")
@login_required
async def create_message(_, info, chat: str, body: str, replyTo=None):
    """ create message with :body for :chat_id replying to :replyTo optionally """
    auth: AuthCredentials = info.context["request"].auth

    chat = await redis.execute("GET", f"chats/{chat}")
    if not chat:
        return {
            "error": "chat is not exist"
        }
    else:
        chat = dict(json.loads(chat))
        message_id = await redis.execute("GET", f"chats/{chat['id']}/next_message_id")
        message_id = int(message_id)
        new_message = {
            "chatId": chat['id'],
            "id": message_id,
            "author": auth.user_id,
            "body": body,
            "createdAt": int(datetime.now(tz=timezone.utc).timestamp())
        }
        if replyTo:
            new_message['replyTo'] = replyTo
        chat['updatedAt'] = new_message['createdAt']
        await redis.execute("SET", f"chats/{chat['id']}", json.dumps(chat))
        print(f"[inbox] creating message {new_message}")
        await redis.execute(
            "SET", f"chats/{chat['id']}/messages/{message_id}", json.dumps(new_message)
        )
        await redis.execute("LPUSH", f"chats/{chat['id']}/message_ids", str(message_id))
        await redis.execute("SET", f"chats/{chat['id']}/next_message_id", str(message_id + 1))

        users = chat["users"]
        for user_slug in users:
            await redis.execute(
                "LPUSH", f"chats/{chat['id']}/unread/{user_slug}", str(message_id)
            )

        result = FollowingResult("NEW", 'chat', new_message)
        await FollowingManager.push('chat', result)

        return {
            "message": new_message,
            "error": None
        }


@mutation.field("updateMessage")
@login_required
async def update_message(_, info, chat_id: str, message_id: int, body: str):
    auth: AuthCredentials = info.context["request"].auth

    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {"error": "chat not exist"}

    message = await redis.execute("GET", f"chats/{chat_id}/messages/{message_id}")
    if not message:
        return {"error": "message  not exist"}

    message = json.loads(message)
    if message["author"] != auth.user_id:
        return {"error": "access denied"}

    message["body"] = body
    message["updatedAt"] = int(datetime.now(tz=timezone.utc).timestamp())

    await redis.execute("SET", f"chats/{chat_id}/messages/{message_id}", json.dumps(message))

    result = FollowingResult("UPDATED", 'chat', message)
    await FollowingManager.push('chat', result)

    return {
        "message": message,
        "error": None
    }


@mutation.field("deleteMessage")
@login_required
async def delete_message(_, info, chat_id: str, message_id: int):
    auth: AuthCredentials = info.context["request"].auth

    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {"error": "chat not exist"}
    chat = json.loads(chat)

    message = await redis.execute("GET", f"chats/{chat_id}/messages/{str(message_id)}")
    if not message:
        return {"error": "message  not exist"}
    message = json.loads(message)
    if message["author"] != auth.user_id:
        return {"error": "access denied"}

    await redis.execute("LREM", f"chats/{chat_id}/message_ids", 0, str(message_id))
    await redis.execute("DEL", f"chats/{chat_id}/messages/{str(message_id)}")

    users = chat["users"]
    for user_id in users:
        await redis.execute("LREM", f"chats/{chat_id}/unread/{user_id}", 0, str(message_id))

    result = FollowingResult("DELETED", 'chat', message)
    await FollowingManager.push(result)

    return {}


@mutation.field("markAsRead")
@login_required
async def mark_as_read(_, info, chat_id: str, messages: [int]):
    auth: AuthCredentials = info.context["request"].auth

    chat = await redis.execute("GET", f"chats/{chat_id}")
    if not chat:
        return {"error": "chat not exist"}

    chat = json.loads(chat)
    users = set(chat["users"])
    if auth.user_id not in users:
        return {"error": "access denied"}

    for message_id in messages:
        await redis.execute("LREM", f"chats/{chat_id}/unread/{auth.user_id}", 0, str(message_id))

    return {
        "error": None
    }


@subscription.source("newMessage")
async def message_generator(_, info: GraphQLResolveInfo):
    print(f"[resolvers.messages] generator {info}")
    auth: AuthCredentials = info.context["request"].auth
    user_id = auth.user_id
    try:
        user_following_chats = await redis.execute("GET", f"chats_by_user/{user_id}")
        if user_following_chats:
            user_following_chats = list(json.loads(user_following_chats))  # chat ids
        else:
            user_following_chats = []
        tasks = []
        updated = {}
        for chat_id in user_following_chats:
            chat = await redis.execute("GET", f"chats/{chat_id}")
            updated[chat_id] = chat['updatedAt']
        user_following_chats_sorted = sorted(user_following_chats, key=lambda x: updated[x], reverse=True)

        for chat_id in user_following_chats_sorted:
            following_chat = Following('chat', chat_id)
            await FollowingManager.register('chat', following_chat)
            chat_task = following_chat.queue.get()
            tasks.append(chat_task)

        while True:
            msg = await asyncio.gather(*tasks)
            yield msg
    finally:
        await FollowingManager.remove('chat', following_chat)


@subscription.field("newMessage")
@login_required
async def message_resolver(message: Message, info: Any):
    return message
