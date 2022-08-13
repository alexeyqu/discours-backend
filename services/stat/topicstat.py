import asyncio
from base.orm import local_session
from services.stat.reacted import ReactedStorage
from services.stat.viewed import ViewedStorage
from services.zine.shoutauthor import ShoutAuthorStorage
from orm.topic import ShoutTopic, TopicFollower
from typing import Dict

class TopicStat:
	shouts_by_topic = {}
	authors_by_topic = {}
	followers_by_topic = {}
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

		print('[stat.topics] authors sorted')
		print('[stat.topics] shouts sorted')
		
		self.followers_by_topic = {}
		followings = session.query(TopicFollower)
		for flw in followings:
			topic = flw.topic
			user = flw.follower
			if topic in self.followers_by_topic:
				self.followers_by_topic[topic].append(user)
			else:
				self.followers_by_topic[topic] = [user]
		print('[stat.topics] followers sorted')

	@staticmethod
	async def get_shouts(topic):
		self = TopicStat
		async with self.lock:
			return self.shouts_by_topic.get(topic, [])

	@staticmethod
	async def get_stat(topic):
		self = TopicStat
		async with self.lock:
			shouts = self.shouts_by_topic.get(topic, [])
			followers = self.followers_by_topic.get(topic, [])
			authors = self.authors_by_topic.get(topic, [])

		return  { 
			"shouts" : len(shouts),
			"authors" : len(authors),
			"followers" : len(followers),
			"viewed": ViewedStorage.get_topic(topic),
			"reacted" : ReactedStorage.get_topic(topic),
			"rating" : ReactedStorage.get_topic_rating(topic),
		}

	@staticmethod
	async def worker():
		self = TopicStat
		while True:
			try:
				with local_session() as session:
					async with self.lock:
						await self.load_stat(session)
						print("[stat.topics] updated")
			except Exception as err:
				print("[stat.topics] errror: %s" % (err))
			await asyncio.sleep(self.period)

