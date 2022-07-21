

import asyncio
from orm.base import local_session
from storages.shoutauthor import ShoutAuthorStorage
from orm.topic import ShoutTopic, TopicFollower


class TopicStat:
	shouts_by_topic = {}
	authors_by_topic = {}
	followers_by_topic = {}
	reactions_by_topic = {}
	lock = asyncio.Lock()
	period = 30*60 #sec

	@staticmethod
	async def load_stat(session):
		self = TopicStat
		self.shouts_by_topic = {}
		self.authors_by_topic = {}
		shout_topics = session.query(ShoutTopic)
		for shout_topic in shout_topics:
			topic = shout_topic.topic
			shout = shout_topic.shout
			if topic in self.shouts_by_topic:
				self.shouts_by_topic[topic].append(shout)
			else:
				self.shouts_by_topic[topic] = [shout]

			authors = await ShoutAuthorStorage.get_authors(shout)
			if topic in self.authors_by_topic:
				self.authors_by_topic[topic].update(authors)
			else:
				self.authors_by_topic[topic] = set(authors)

		print('[storage.topicstat] authors sorted')
		print('[storage.topicstat] shouts sorted')
		
		self.followers_by_topic = {}
		followings = session.query(TopicFollower)
		for flw in followings:
			topic = flw.topic
			user = flw.follower
			if topic in self.followers_by_topic:
				self.followers_by_topic[topic].append(user)
			else:
				self.followers_by_topic[topic] = [user]
		print('[storage.topicstat] followers sorted')

	@staticmethod
	async def get_shouts(topic):
		self = TopicStat
		async with self.lock:
			return self.shouts_by_topic.get(topic, [])

	@staticmethod
	async def get_stat(topic) -> dict:
		self = TopicStat
		async with self.lock:
			shouts = self.shouts_by_topic.get(topic, [])
			followers = self.followers_by_topic.get(topic, [])
			authors = self.authors_by_topic.get(topic, [])
			reactions = self.reactions_by_topic.get(topic, [])

		return  { 
			"shouts" : len(shouts),
			"authors" : len(authors),
			"followers" : len(followers),
			"reactions" : len(reactions)
		}

	@staticmethod
	async def worker():
		self = TopicStat
		while True:
			try:
				with local_session() as session:
					async with self.lock:
						await self.load_stat(session)
						print("[storage.topicstat] updated")
			except Exception as err:
				print("[storage.topicstat] errror: %s" % (err))
			await asyncio.sleep(self.period)

