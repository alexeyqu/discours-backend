from orm import Comment, CommentRating
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio
from datetime import datetime

class CommentResult:
	def __init__(self, status, comment):
		self.status = status
		self.comment = comment

class CommentSubscription:
	queue = asyncio.Queue()

	def __init__(self, shout_slug):
		self.shout_slug = shout_slug

#TODO: one class for MessageSubscription and CommentSubscription
class CommentSubscriptions:
	lock = asyncio.Lock()
	subscriptions = []

	@staticmethod
	async def register_subscription(subs):
		self = CommentSubscriptions
		async with self.lock:
			self.subscriptions.append(subs)
	
	@staticmethod
	async def del_subscription(subs):
		self = CommentSubscriptions
		async with self.lock:
			self.subscriptions.remove(subs)
	
	@staticmethod
	async def put(comment_result):
		self = CommentSubscriptions
		async with self.lock:
			for subs in self.subscriptions:
				if comment_result.comment.shout == subs.shout_slug:
					subs.queue.put_nowait(comment_result)

@mutation.field("createComment")
@login_required
async def create_comment(_, info, body, shout, replyTo = None):
	auth = info.context["request"].auth
	user_id = auth.user_id

	comment = Comment.create(
		author = user_id,
		body = body,
		shout = shout,
		replyTo = replyTo
		)

	result = CommentResult("NEW", comment)
	await CommentSubscriptions.put(result)

	return {"comment": comment}

@mutation.field("updateComment")
@login_required
async def update_comment(_, info, id, body):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == id).first()
		if not comment:
			return {"error": "invalid comment id"}
		if comment.author != user_id:
			return {"error": "access denied"}
		
		comment.body = body
		comment.updatedAt = datetime.now()
		
		session.commit()

	result = CommentResult("UPDATED", comment)
	await CommentSubscriptions.put(result)

	return {"comment": comment}

@mutation.field("deleteComment")
@login_required
async def delete_comment(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == id).first()
		if not comment:
			return {"error": "invalid comment id"}
		if comment.author != user_id:
			return {"error": "access denied"}

		comment.deletedAt = datetime.now()
		session.commit()

	result = CommentResult("DELETED", comment)
	await CommentSubscriptions.put(result)

	return {}

@mutation.field("rateComment")
@login_required
async def rate_comment(_, info, id, value):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		comment = session.query(Comment).filter(Comment.id == id).first()
		if not comment:
			return {"error": "invalid comment id"}

		rating = session.query(CommentRating).\
			filter(CommentRating.comment_id == id and CommentRating.createdBy == user_id).first()
		if rating:
			rating.value = value
			session.commit()
	
	if not rating:
		CommentRating.create(
			comment_id = id,
			createdBy = user_id,
			value = value)

	result = CommentResult("UPDATED_RATING", comment)
	await CommentSubscriptions.put(result)

	return {}

@subscription.source("commentUpdated")
async def comment_generator(obj, info, shout):
	try:
		subs = CommentSubscription(shout)
		await CommentSubscriptions.register_subscription(subs)
		while True:
			result = await subs.queue.get()
			yield result
	finally:
		await CommentSubscriptions.del_subscription(subs)

@subscription.field("commentUpdated")
def comment_resolver(result, info, shout):
	return result
