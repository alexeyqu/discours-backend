import re

from bs4 import BeautifulSoup
from dateutil.parser import parse
from sqlalchemy.exc import IntegrityError

from base.orm import local_session
from orm.user import AuthorFollower, User, UserRating


def migrate(entry):
    if "subscribedTo" in entry:
        del entry["subscribedTo"]
    email = entry["emails"][0]["address"]
    user_dict = {
        "oid": entry["_id"],
        "roles": [],
        "ratings": [],
        "username": email,
        "email": email,
        "createdAt": parse(entry["createdAt"]),
        "emailConfirmed": ("@discours.io" in email) or bool(entry["emails"][0]["verified"]),
        "muted": False,  # amnesty
        "bio": entry["profile"].get("bio", ""),
        "links": [],
        "name": "anonymous",
        "password": entry["services"]["password"].get("bcrypt")
    }

    if "updatedAt" in entry:
        user_dict["updatedAt"] = parse(entry["updatedAt"])
    if "wasOnineAt" in entry:
        user_dict["lastSeen"] = parse(entry["wasOnlineAt"])
    if entry.get("profile"):
        # slug
        slug = entry["profile"].get("path").lower()
        slug = re.sub('[^0-9a-zA-Z]+', '-', slug).strip()
        user_dict["slug"] = slug
        bio = (entry.get("profile", {"bio": ""}).get("bio") or "").replace('\(', '(').replace('\)', ')')
        bio_html = BeautifulSoup(bio, features="lxml").text
        if bio == bio_html:
            user_dict["bio"] = bio
        else:
            user_dict["about"] = bio

        # userpic
        try:
            user_dict["userpic"] = (
                "https://assets.discours.io/unsafe/100x/"
                + entry["profile"]["thumborId"]
            )
        except KeyError:
            try:
                user_dict["userpic"] = entry["profile"]["image"]["url"]
            except KeyError:
                user_dict["userpic"] = ""

        # name
        fn = entry["profile"].get("firstName", "")
        ln = entry["profile"].get("lastName", "")
        name = fn if fn else ""
        name = (name + " " + ln) if ln else name
        if not name:
            name = slug if slug else "anonymous"
        name = (
            entry["profile"]["path"].lower().strip().replace(" ", "-")
            if len(name) < 2
            else name
        )
        user_dict["name"] = name

        # links
        fb = entry["profile"].get("facebook", False)
        if fb:
            user_dict["links"].append(fb)
        vk = entry["profile"].get("vkontakte", False)
        if vk:
            user_dict["links"].append(vk)
        tr = entry["profile"].get("twitter", False)
        if tr:
            user_dict["links"].append(tr)
        ws = entry["profile"].get("website", False)
        if ws:
            user_dict["links"].append(ws)

    # some checks
    if not user_dict["slug"] and len(user_dict["links"]) > 0:
        user_dict["slug"] = user_dict["links"][0].split("/")[-1]

    user_dict["slug"] = user_dict.get("slug", user_dict["email"].split("@")[0])
    oid = user_dict["oid"]
    user_dict["slug"] = user_dict["slug"].lower().strip().replace(" ", "-")
    try:
        user = User.create(**user_dict.copy())
    except IntegrityError:
        print("[migration] cannot create user " + user_dict["slug"])
        with local_session() as session:
            old_user = (
                session.query(User).filter(User.slug == user_dict["slug"]).first()
            )
            old_user.oid = oid
            old_user.password = user_dict["password"]
            session.commit()
            user = old_user
            if not user:
                print("[migration] ERROR: cannot find user " + user_dict["slug"])
                raise Exception
    user_dict["id"] = user.id
    return user_dict


def post_migrate():
    old_discours_dict = {
        "slug": "old-discours",
        "username": "old-discours",
        "email": "old@discours.io",
        "name": "Просмотры на старой версии сайта"
    }

    with local_session() as session:
        old_discours_user = User.create(**old_discours_dict)
        session.add(old_discours_user)
        session.commit()


def migrate_2stage(entry, id_map):
    ce = 0
    for rating_entry in entry.get("ratings", []):
        rater_oid = rating_entry["createdBy"]
        rater_slug = id_map.get(rater_oid)
        if not rater_slug:
            ce += 1
            # print(rating_entry)
            continue
        oid = entry["_id"]
        author_slug = id_map.get(oid)

        with local_session() as session:
            try:
                rater = session.query(User).where(User.slug == rater_slug).one()
                user = session.query(User).where(User.slug == author_slug).one()

                user_rating_dict = {
                    "value": rating_entry["value"],
                    "rater": rater.id,
                    "user": user.id,
                }

                user_rating = UserRating.create(**user_rating_dict)
                if user_rating_dict['value'] > 0:
                    af = AuthorFollower.create(
                        author=user.id,
                        follower=rater.id,
                        auto=True
                    )
                    session.add(af)
                session.add(user_rating)
                session.commit()
            except IntegrityError:
                print("[migration] cannot rate " + author_slug + "`s by " + rater_slug)
            except Exception as e:
                print(e)
    return ce
