from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import and_, select, desc

from auth.authenticate import login_required
from base.orm import local_session
from base.resolvers import mutation, query
from orm.collection import ShoutCollection
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from resolvers.community import community_follow, community_unfollow
from resolvers.profile import author_follow, author_unfollow
from resolvers.reactions import reactions_follow, reactions_unfollow
from resolvers.topics import topic_follow, topic_unfollow
from services.stat.viewed import ViewedStorage
from services.zine.shoutauthor import ShoutAuthorStorage
from services.zine.shoutscache import ShoutsCache


@mutation.field("incrementView")
async def increment_view(_, _info, shout):
    async with ViewedStorage.lock:
        return ViewedStorage.increment(shout)


@query.field("topViewed")
async def top_viewed(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.top_viewed[offset : offset + limit]


@query.field("topMonth")
async def top_month(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.top_month[offset : offset + limit]


@query.field("topCommented")
async def top_commented(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.top_commented[offset : offset + limit]


@query.field("topOverall")
async def top_overall(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.top_overall[offset : offset + limit]


@query.field("recentPublished")
async def recent_published(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_published[offset : offset + limit]


@query.field("recentAll")
async def recent_all(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_all[offset : offset + limit]


@query.field("recentReacted")
async def recent_reacted(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_reacted[offset : offset + limit]


@query.field("recentCommented")
async def recent_commented(_, _info, offset, limit):
    async with ShoutsCache.lock:
        return ShoutsCache.recent_commented[offset : offset + limit]


@query.field("getShoutBySlug")
async def get_shout_by_slug(_, info, slug):
    all_fields = [
        node.name.value for node in info.field_nodes[0].selection_set.selections
    ]
    selected_fields = set(["authors", "topics"]).intersection(all_fields)
    select_options = [selectinload(getattr(Shout, field)) for field in selected_fields]
    with local_session() as session:
        # s = text(open("src/queries/shout-by-slug.sql", "r").read() % slug)
        shout = (
            session.query(Shout)
            .options(select_options)
            .filter(Shout.slug == slug)
            .first()
        )

        if not shout:
            print(f"shout with slug {slug} not exist")
            return {"error": "shout not found"}
        else:
            for a in shout.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(slug, a.slug)
    return shout


@query.field("searchQuery")
async def get_search_results(_, _info, query, offset, limit):
    # TODO: remove the copy of searchByTopics
    # with search ranking query
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutTopic)
            .where(and_(ShoutTopic.topic.in_(query), bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(limit)
            .offset(offset)
        )

    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
        s.stat.relevance = 1  # FIXME: expecting search engine rated relevance
    return shouts


@query.field("shoutsByTopics")
async def shouts_by_topics(_, _info, slugs, offset, limit):
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutTopic)
            .where(and_(ShoutTopic.topic.in_(slugs), bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(limit)
            .offset(offset)
        )

    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
    return shouts


@query.field("shoutsByCollection")
async def shouts_by_collection(_, _info, collection, offset, limit):
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutCollection, ShoutCollection.collection == collection)
            .where(and_(ShoutCollection.shout == Shout.slug, bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(limit)
            .offset(offset)
        )
    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
    return shouts


@query.field("shoutsByAuthors")
async def shouts_by_authors(_, _info, slugs, offset, limit):
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(ShoutAuthor)
            .where(and_(ShoutAuthor.user.in_(slugs), bool(Shout.publishedAt)))
            .order_by(desc(Shout.publishedAt))
            .limit(limit)
            .offset(offset)
        )

    for s in shouts:
        for a in s.authors:
            a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
    return shouts


SINGLE_COMMUNITY = True


@query.field("shoutsByCommunities")
async def shouts_by_communities(_, info, slugs, offset, limit):
    if SINGLE_COMMUNITY:
        return recent_published(_, info, offset, limit)
    else:
        with local_session() as session:
            # TODO fix postgres high load
            shouts = (
                session.query(Shout)
                .distinct()
                .join(ShoutTopic)
                .where(
                    and_(
                        bool(Shout.publishedAt),
                        ShoutTopic.topic.in_(
                            select(Topic.slug).where(Topic.community.in_(slugs))
                        ),
                    )
                )
                .order_by(desc("publishedAt"))
                .limit(limit)
                .offset(offset)
            )

        for s in shouts:
            for a in s.authors:
                a.caption = await ShoutAuthorStorage.get_author_caption(s.slug, a.slug)
        return shouts


@mutation.field("follow")
@login_required
async def follow(_, info, what, slug):
    user = info.context["request"].user
    try:
        if what == "AUTHOR":
            author_follow(user, slug)
        elif what == "TOPIC":
            topic_follow(user, slug)
        elif what == "COMMUNITY":
            community_follow(user, slug)
        elif what == "REACTIONS":
            reactions_follow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}


@mutation.field("unfollow")
@login_required
async def unfollow(_, info, what, slug):
    user = info.context["request"].user

    try:
        if what == "AUTHOR":
            author_unfollow(user, slug)
        elif what == "TOPIC":
            topic_unfollow(user, slug)
        elif what == "COMMUNITY":
            community_unfollow(user, slug)
        elif what == "REACTIONS":
            reactions_unfollow(user, slug)
    except Exception as e:
        return {"error": str(e)}

    return {}
