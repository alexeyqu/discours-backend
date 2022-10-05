import asyncio
from importlib import import_module

from ariadne import load_schema_from_path, make_executable_schema
from ariadne.asgi import GraphQL
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Route

from auth.authenticate import JWTAuthenticate
from auth.oauth import oauth_login, oauth_authorize
from base.redis import redis
from base.resolvers import resolvers
from resolvers.auth import confirm_email_handler
from resolvers.zine import ShoutsCache
from services.main import storages_init
from services.stat.reacted import ReactedStorage
from services.stat.topicstat import TopicStat
from services.stat.viewed import ViewedStorage
from services.zine.gittask import GitTask
from services.zine.shoutauthor import ShoutAuthorStorage
import_module("resolvers")
schema = make_executable_schema(load_schema_from_path("schema.graphql"), resolvers)  # type: ignore

middleware = [
    Middleware(AuthenticationMiddleware, backend=JWTAuthenticate()),
    Middleware(SessionMiddleware, secret_key="!secret"),
]


async def start_up():
    await redis.connect()
    viewed_storage_task = asyncio.create_task(ViewedStorage.worker())
    print(viewed_storage_task)
    reacted_storage_task = asyncio.create_task(ReactedStorage.worker())
    print(reacted_storage_task)
    shouts_cache_task = asyncio.create_task(ShoutsCache.worker())
    print(shouts_cache_task)
    shout_author_task = asyncio.create_task(ShoutAuthorStorage.worker())
    print(shout_author_task)
    topic_stat_task = asyncio.create_task(TopicStat.worker())
    print(topic_stat_task)
    git_task = asyncio.create_task(GitTask.git_task_worker())
    print(git_task)
    await storages_init()
    print()


async def shutdown():
    await redis.disconnect()


routes = [
    Route("/oauth/{provider}", endpoint=oauth_login),
    Route("/oauth_authorize", endpoint=oauth_authorize),
    Route("/confirm-email/{token}", endpoint=confirm_email_handler),  # should be called on client
]

app = Starlette(
    debug=True,
    on_startup=[start_up],
    on_shutdown=[shutdown],
    middleware=middleware,
    routes=routes,
)
app.mount("/", GraphQL(schema, debug=True))
