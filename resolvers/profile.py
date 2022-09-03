from datetime import datetime
from orm.user import User, UserRole, Role, UserRating, AuthorFollower
from services.auth.users import UserStorage
from orm.shout import Shout
from orm.reaction import Reaction
from base.orm import local_session
from orm.topic import Topic, TopicFollower
from base.resolvers import mutation, query
from resolvers.community import get_followed_communities
from resolvers.reactions import get_shout_reactions
from auth.authenticate import login_required
from resolvers.inbox import get_unread_counter
from sqlalchemy import and_, desc
from sqlalchemy.orm import selectinload
from typing import List


@query.field("userReactedShouts")
async def get_user_reacted_shouts(_, info, slug, page, size) -> List[Shout]:
    user = await UserStorage.get_user_by_slug(slug)
    if not user:
        return []
    with local_session() as session:
        shouts = (
            session.query(Shout)
            .join(Reaction)
            .where(Reaction.createdBy == user.slug)
            .order_by(desc(Reaction.createdAt))
            .limit(size)
            .offset(page * size)
            .all()
        )
    return shouts


@query.field("userFollowedTopics")
@login_required
def get_followed_topics(_, slug) -> List[Topic]:
    rows = []
    with local_session() as session:
        rows = (
            session.query(Topic)
            .join(TopicFollower)
            .where(TopicFollower.follower == slug)
            .all()
        )
    return rows


@query.field("userFollowedAuthors")
def get_followed_authors(_, slug) -> List[User]:
    authors = []
    with local_session() as session:
        authors = (
            session.query(User)
            .join(AuthorFollower, User.slug == AuthorFollower.author)
            .where(AuthorFollower.follower == slug)
            .all()
        )
    return authors


@query.field("userFollowers")
async def user_followers(_, slug) -> List[User]:
    with local_session() as session:
        users = (
            session.query(User)
            .join(AuthorFollower, User.slug == AuthorFollower.follower)
            .where(AuthorFollower.author == slug)
            .all()
        )
    return users


# for mutation.field("refreshSession")
async def get_user_info(slug):
    return {
        "unread": await get_unread_counter(slug),
        "topics": [t.slug for t in get_followed_topics(0, slug)],
        "authors": [a.slug for a in get_followed_authors(0, slug)],
        "reactions": [r.shout for r in get_shout_reactions(0, slug)],
        "communities": [c.slug for c in get_followed_communities(0, slug)],
    }


@mutation.field("refreshSession")
@login_required
async def get_current_user(_, info):
    user = info.context["request"].user
    with local_session() as session:
        user.lastSeen = datetime.now()
        user.save()
        session.commit()
    return {
        "token": "",  # same token?
        "user": user,
        "info": await get_user_info(user.slug),
    }


@query.field("getUsersBySlugs")
async def get_users_by_slugs(_, info, slugs):
    with local_session() as session:
        users = (
            session.query(User)
            .options(selectinload(User.ratings))
            .filter(User.slug in slugs)
            .all()
        )
    return users


@query.field("getUserRoles")
async def get_user_roles(_, info, slug):
    with local_session() as session:
        user = session.query(User).where(User.slug == slug).first()
        roles = (
            session.query(Role)
            .options(selectinload(Role.permissions))
            .join(UserRole)
            .where(UserRole.user_id == user.id)
            .all()
        )
    return roles


@mutation.field("updateProfile")
@login_required
async def update_profile(_, info, profile):
    auth = info.context["request"].auth
    user_id = auth.user_id
    with local_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            User.update(user, **profile)
        session.commit()
    return {}


@mutation.field("rateUser")
@login_required
async def rate_user(_, info, slug, value):
    user = info.context["request"].user
    with local_session() as session:
        rating = (
            session.query(UserRating)
            .filter(and_(UserRating.rater == user.slug, UserRating.user == slug))
            .first()
        )
        if rating:
            rating.value = value
            session.commit()
            return {}
    try:
        UserRating.create(rater=user.slug, user=slug, value=value)
    except Exception as err:
        return {"error": err}
    return {}


# for mutation.field("follow")
def author_follow(user, slug):
    AuthorFollower.create(follower=user.slug, author=slug)


# for mutation.field("unfollow")
def author_unfollow(user, slug):
    with local_session() as session:
        flw = (
            session.query(AuthorFollower)
            .filter(
                and_(
                    AuthorFollower.follower == user.slug, AuthorFollower.author == slug
                )
            )
            .first()
        )
        if not flw:
            raise Exception("[resolvers.profile] follower not exist, cant unfollow")
        else:
            session.delete(flw)
            session.commit()


@query.field("authorsAll")
def get_authors_all(_, info, page, size):
    end = page * size
    start = end - size
    return list(UserStorage.get_all_users())[start:end]  # type: ignore
