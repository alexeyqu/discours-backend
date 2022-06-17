# discoursio-api

Tech stack:

- pyjwt
- redis
- ariadne
- starlette

# Local development 

Install deps first

on osx
```
brew install redis poetry nginx
brew services start redis
```

on debian/ubuntu
```
apt install redis python-poetry nginx
```

Then run nginx, redis and API server

```
redis-server

cp nginx.conf /usr/local/etc/nginx/.
nginx -s reload

poetry install
poetry run python server.py
poetry run python server.py inbox
```

## Data prepare

Also, you'll need to migrate some data

```
poetry run python migrate.py all
```

# How to do an authorized request

Put the header 'Auth' with token from signInQuery or registerQuery.

