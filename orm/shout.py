from typing import List
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime

from orm import Permission
from orm.base import Base


class Shout(Base):
	__tablename__ = 'shout'

	author_id: str = Column(ForeignKey("user.id"), nullable=False, comment="Author")
	body: str = Column(String, nullable=False, comment="Body")
	createdAt: str = Column(DateTime, nullable=False, default = datetime.now, comment="Created at")
	updatedAt: str = Column(DateTime, nullable=True, comment="Updated at")

	# TODO: add all the fields
