import sqlalchemy
from orm import User, Role, UserRating
from orm.user import EmailSubscription
import frontmatter
from dateutil.parser import parse
from migration.html2text import html2text
from orm.base import local_session

def migrate(entry):
	'''

	type User {
		username: String! # email
		createdAt: DateTime!
		email: String
		password: String
		oauth: String # provider:token
		name: String # to display
		userpic: String
		links: [String]
		emailConfirmed: Boolean # should contain all emails too
		id: Int!
		muted: Boolean
		roles: [Role]
		updatedAt: DateTime
		wasOnlineAt: DateTime
		ratings: [Rating]
		slug: String
		bio: String
		notifications: [Int]
	}

	'''
	res = {}
	res['old_id'] = entry['_id']
	res['password'] = entry['services']['password'].get('bcrypt', '')
	del entry['services']
	if 'subscribedTo' in entry: #TODO: use subscribedTo
		del entry['subscribedTo']
	res['username'] = entry['emails'][0]['address']
	res['email'] = res['username']
	res['wasOnlineAt'] = parse(entry.get('loggedInAt', entry['createdAt']))
	res['emailConfirmed'] = entry['emails'][0]['verified']
	res['createdAt'] = parse(entry['createdAt'])
	res['roles'] = [] # entry['roles'] # roles by community
	res['ratings'] = [] # entry['ratings']
	res['notifications'] = []
	res['links'] = []
	res['muted'] = False
	res['name'] = 'anonymous'
	if entry.get('profile'):
		# slug
		res['slug'] = entry['profile'].get('path')
		res['bio'] = entry['profile'].get('bio','')

		# userpic
		try: res['userpic'] = 'https://assets.discours.io/unsafe/100x/' + entry['profile']['thumborId']
		except KeyError:
			try: res['userpic'] = entry['profile']['image']['url']
			except KeyError: res['userpic'] = ''

		# name
		fn = entry['profile'].get('firstName', '')
		ln = entry['profile'].get('lastName', '')
		name = res['slug'] if res['slug'] else 'anonymous'
		name = fn if fn else name
		name = (name + ' ' + ln) if ln else name
		name = entry['profile']['path'].lower().replace(' ', '-') if len(name) < 2 else name
		res['name'] = name

		# links
		fb = entry['profile'].get('facebook', False)
		if fb:
			res['links'].append(fb)
		vk = entry['profile'].get('vkontakte', False)
		if vk:
			res['links'].append(vk)
		tr = entry['profile'].get('twitter', False)
		if tr:
			res['links'].append(tr)
		ws = entry['profile'].get('website', False)
		if ws:
			res['links'].append(ws)

	# some checks
	if not res['slug'] and len(res['links']) > 0: res['slug'] = res['links'][0].split('/')[-1]

	res['slug'] = res.get('slug', res['email'].split('@')[0])
	old = res['old_id']
	user = User.create(**res.copy())
	res['id'] = user.id
	return res

def migrate_email_subscription(entry):
	res = {}
	res["email"] = entry["email"]
	res["createdAt"] = parse(entry["createdAt"])
	subscription = EmailSubscription.create(**res)

def migrate_2stage(entry, id_map):
	ce = 0
	for rating_entry in entry.get('ratings',[]):
		rater_old_id = rating_entry['createdBy']
		rater_slug = id_map.get(rater_old_id)
		if not rater_slug:
			ce +=1
			# print(rating_entry)
			continue
		old_id = entry['_id']
		user_rating_dict = {
			'value': rating_entry['value'],
			'rater': rater_slug,
			'user': id_map.get(old_id)
		}
		with local_session() as session:
			try:
				user_rating = UserRating.create(**user_rating_dict)
			except sqlalchemy.exc.IntegrityError:
				print('[migration] duplicate rating solving for ' + rater_slug)
				old_rating = session.query(UserRating).filter(UserRating.rater == rater_slug).first()
				old_rating.value = rating_entry['value'] + old_rating.value
			except Exception as e:
				print(e)
	return ce
