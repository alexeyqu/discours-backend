from datetime import datetime
import time
import jwt
from base.exceptions import ExpiredToken, InvalidToken
from validations.auth import TokenPayload
from settings import JWT_ALGORITHM, JWT_SECRET_KEY


class JWTCodec:
    @staticmethod
    def encode(user_id: int, exp: datetime) -> str:
        issued = int(time.mktime(datetime.now().timetuple()))
        print('[jwtcodec] issued at %r' % issued)
        expires = time.mktime(exp.timetuple())
        print('[jwtcodec] expires at %r' % expires)
        payload = {
            "user_id": user_id,
            # "user_email": user.email,  # less secure
            # "device": device,  # no use cases
            "exp": expires,
            "iat": issued,
            "iss": "discours"
        }
        try:
            return jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM)
        except Exception as e:
            print('[jwtcodec] JWT encode error %r' % e)

    @staticmethod
    def decode(token: str, verify_exp: bool = True) -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                key=JWT_SECRET_KEY,
                options={
                    "verify_exp": verify_exp,
                    # "verify_signature": False
                },
                algorithms=[JWT_ALGORITHM],
                issuer="discours"
            )
            r = TokenPayload(**payload)
            print('[jwtcodec] debug payload %r' % r)
            return r
        except jwt.ExpiredSignatureError:
            raise ExpiredToken('check token lifetime')
        except jwt.InvalidTokenError:
            raise InvalidToken('token is not valid')
        except jwt.InvalidSignatureError:
            raise InvalidToken('token is not valid')
        except jwt.InvalidIssuedAtError:
            raise ExpiredToken('check token issued time')
