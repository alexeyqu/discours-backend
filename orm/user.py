from typing import List
from datetime import datetime

from sqlalchemy import Table, Column, Integer, String, ForeignKey, Boolean, DateTime, JSON as JSONType
from sqlalchemy.orm import relationship, selectinload

from orm import RoleStorage
from orm.base import Base, local_session
from orm.rbac import Role
from orm.topic import Topic

import asyncio

class UserNotifications(Base):
	__tablename__ = 'user_notifications'

	id: int = Column(Integer, primary_key = True)
	user_id: int = Column(Integer, ForeignKey("user.id"))
	kind: str = Column(String, ForeignKey("notification.kind"))
	values: JSONType = Column(JSONType, nullable = True) # [ <var1>, .. ]

class UserRating(Base):
	__tablename__ = "user_rating"

	id = None
	rater_id = Column(ForeignKey('user.id'), primary_key = True)
	user_id = Column(ForeignKey('user.id'), primary_key = True)
	value = Column(Integer)

class UserRole(Base):
	__tablename__ = "user_role"

	id = None
	user_id = Column(ForeignKey('user.id'), primary_key = True)
	role_id = Column(ForeignKey('role.id'), primary_key = True)

UserTopics = Table("user_topics",
	Base.metadata,
	Column('user_id', Integer, ForeignKey('user.id'), primary_key = True),
	Column('topic_id', Integer, ForeignKey('topic.id'), primary_key = True)
)

class User(Base):
	__tablename__ = "user"

	email: str = Column(String, unique=True, nullable=False, comment="Email")
	username: str = Column(String, nullable=False, comment="Login")
	password: str = Column(String, nullable=True, comment="Password")
	bio: str = Column(String, nullable=True, comment="Bio")
	userpic: str = Column(String, nullable=True, comment="Userpic")
	name: str = Column(String, nullable=True, comment="Display name")
	rating: int = Column(Integer, nullable=True, comment="Rating")
	slug: str = Column(String, unique=True, comment="User's slug")
	muted: bool = Column(Boolean, default=False)
	emailConfirmed: bool = Column(Boolean, default=False)
	createdAt: DateTime = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	wasOnlineAt: DateTime = Column(DateTime, nullable=False, default = datetime.now, comment="Was online at")
	links: JSONType = Column(JSONType, nullable=True, comment="Links")
	oauth: str = Column(String, nullable=True)
	notifications = relationship(lambda: UserNotifications)
	ratings = relationship(UserRating, foreign_keys=UserRating.user_id)
	roles = relationship(lambda: Role, secondary=UserRole.__tablename__)
	topics = relationship(lambda: Topic, secondary=UserTopics)
	old_id: str = Column(String, nullable = True)

	async def get_permission(self):
		scope = {}
		for user_role in self.roles:
			role = await RoleStorage.get_role(user_role.id)
			for p in role.permissions:
				if not p.resource_id in scope:
					scope[p.resource_id] = set()
				scope[p.resource_id].add(p.operation_id)
		return scope

class UserStorage:
	users = {}
	lock = asyncio.Lock()

	@staticmethod
	def init(session):
		self = UserStorage
		users = session.query(User).\
			options(selectinload(User.roles)).all()
		self.users = dict([(user.id, user) for user in users])

	@staticmethod
	async def get_user(id):
		self = UserStorage
		async with self.lock:
			return self.users.get(id)

	@staticmethod
	async def add_user(user):
		self = UserStorage
		async with self.lock:
			self.users[id] = user

	@staticmethod
	async def del_user(id):
		self = UserStorage
		async with self.lock:
			del self.users[id]


if __name__ == "__main__":
	print(User.get_permission(user_id=1))
