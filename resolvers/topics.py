from orm import Topic, TopicSubscription, TopicStorage, Shout, User
from orm.shout import TopicStat, ShoutAuthorStorage
from orm.user import UserStorage
from orm.base import local_session
from resolvers.base import mutation, query
from auth.authenticate import login_required
import asyncio

from sqlalchemy import func, and_

@query.field("topicsAll")
async def topics_by_slugs(_, info, slugs = None):
	with local_session() as session:
		topics = await TopicStorage.get_topics(slugs)
	all_fields = [node.name.value for node in info.field_nodes[0].selection_set.selections]
	if "stat" in all_fields:
		for topic in topics:
			topic.stat = await TopicStat.get_stat(topic.slug)
	return topics

@query.field("topicsByCommunity")
async def topics_by_community(_, info, community):
	with local_session() as session:
		topics = await TopicStorage.get_topics_by_community(community)
	all_fields = [node.name.value for node in info.field_nodes[0].selection_set.selections]
	if "stat" in all_fields:
		for topic in topics:
			topic.stat = await TopicStat.get_stat(topic.slug)
	return topics
	
@query.field("topicsByAuthor")
async def topics_by_author(_, info, author):
	slugs = set()
	with local_session() as session:
		shouts = session.query(Shout).\
			filter(Shout.authors.any(User.slug == author))
		for shout in shouts:
			slugs.update([topic.slug for topic in shout.topics])
	return await TopicStorage.get_topics(slugs)

@mutation.field("createTopic")
@login_required
async def create_topic(_, info, input):
	new_topic = Topic.create(**input)
	await TopicStorage.add_topic(new_topic)

	return { "topic" : new_topic }

@mutation.field("updateTopic")
@login_required
async def update_topic(_, info, input):
	slug = input["slug"]

	session = local_session()
	topic = session.query(Topic).filter(Topic.slug == slug).first()

	if not topic:
		return { "error" : "topic not found" }

	topic.update(input)
	session.commit()
	session.close()

	await TopicStorage.add_topic(topic)

	return { "topic" : topic }

def topic_subscribe(user, slug):
	TopicSubscription.create(
		subscriber = user.slug, 
		topic = slug)

def topic_unsubscribe(user, slug):
	with local_session() as session:
		sub = session.query(TopicSubscription).\
			filter(and_(TopicSubscription.subscriber == user.slug, TopicSubscription.topic == slug)).\
			first()
		if not sub:
			raise Exception("subscription not exist")
		session.delete(sub)
		session.commit()
