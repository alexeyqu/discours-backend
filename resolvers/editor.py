from orm import Proposal, ProposalRating
from orm.base import local_session
from resolvers.base import mutation, query, subscription
from auth.authenticate import login_required
import asyncio
from datetime import datetime

class ProposalResult:
	def __init__(self, status, proposal):
		self.status = status
		self.proposal = proposal

@mutation.field("createProposal")
@login_required
async def create_proposal(_, info, body, shout, range = None):
	auth = info.context["request"].auth
	user_id = auth.user_id

	proposal = Proposal.create(
		createdBy = user_id,
		body = body,
		shout = shout,
		range = range
		)

	result = ProposalResult("NEW", proposal)
	await ProposalSubscriptions.put(result)

	return {"proposal": proposal}

@mutation.field("updateProposal")
@login_required
async def update_proposal(_, info, id, body):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
        shout = session.query(Shout.slug === proposal.shout)
		if not proposal:
			return {"error": "invalid proposal id"}
		if proposal.author != user_id:
			return {"error": "access denied"}
		proposal.body = body
		proposal.updatedAt = datetime.now()
		session.commit()

	result = ProposalResult("UPDATED", proposal)
	await ProposalSubscriptions.put(result)

	return {"proposal": proposal}

@mutation.field("deleteProposal")
@login_required
async def delete_proposal(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		if not proposal:
			return {"error": "invalid proposal id"}
		if proposal.createdBy != user_id: 
			return {"error": "access denied"}

		proposal.deletedAt = datetime.now()
		session.commit()

	result = ProposalResult("DELETED", proposal)
	await ProposalSubscriptions.put(result)

	return {}

@mutation.field("rateProposal")
@login_required
async def rate_proposal(_, info, id, value):
	auth = info.context["request"].auth
	user_id = auth.user_id
	
	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		if not proposal:
			return {"error": "invalid proposal id"}

		rating = session.query(ProposalRating).\
			filter(ProposalRating.proposal_id == id and ProposalRating.createdBy == user_id).first()
		if rating:
			rating.value = value
			session.commit()
	
	if not rating:
		ProposalRating.create(
			proposal_id = id,
			createdBy = user_id,
			value = value)

	result = ProposalResult("UPDATED_RATING", proposal)
	await ProposalSubscriptions.put(result)

	return {}


@mutation.field("acceptProposal")
@login_required
async def accept_proposal(_, info, id):
	auth = info.context["request"].auth
	user_id = auth.user_id

	with local_session() as session:
		proposal = session.query(Proposal).filter(Proposal.id == id).first()
		if not proposal:
			return {"error": "invalid proposal id"}
		if proposal.acceptedBy == user_id: # TODO: manage ACL here to give access all editors
			return {"error": "access denied"}

		proposal.acceptedAt = datetime.now()
		proposal.acceptedBy = user_id 
		session.commit()

	result = ProposalResult("ACCEPTED", proposal)
	await ProposalSubscriptions.put(result)

	return {}
