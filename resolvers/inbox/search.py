import json

from auth.authenticate import login_required
from auth.credentials import AuthCredentials
from base.redis import redis
from base.resolvers import query
from base.orm import local_session
from orm.user import AuthorFollower, User


@query.field("searchRecipients")
@login_required
async def search_recipients(_, info, query: str, limit: int = 50, offset: int = 0):
    result = []
    # TODO: maybe redis scan?
    auth: AuthCredentials = info.context["request"].auth
    talk_before = await redis.execute("GET", f"/chats_by_user/{auth.user_id}")
    if talk_before:
        talk_before = list(json.loads(talk_before))[offset:offset + limit]
        for chat_id in talk_before:
            members = await redis.execute("GET", f"/chats/{chat_id}/users")
            if members:
                members = list(json.loads(members))
                for member in members:
                    if member.startswith(query):
                        if member not in result:
                            result.append(member)

    more_amount = limit - len(result)

    with local_session() as session:
        # followings
        result += session.query(AuthorFollower.author).join(
            User, User.id == AuthorFollower.follower
        ).where(
            User.slug.startswith(query)
        ).offset(offset + len(result)).limit(more_amount)

        more_amount = limit
        # followers
        result += session.query(AuthorFollower.follower).join(
            User, User.id == AuthorFollower.author
        ).where(
            User.slug.startswith(query)
        ).offset(offset + len(result)).limit(offset + len(result) + limit)
    return {
        "members": list(result),
        "error": None
    }
