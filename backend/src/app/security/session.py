"""Signed session cookie helpers.

Replaces the old plain, unsigned `creator_session` cookie (bare `creator.id`) with an
`itsdangerous`-signed token, per the "signed session cookie" decision: same shape (cookie ->
creator id -> DB lookup via a dependency) but the client can no longer forge it by editing the
cookie value. This intentionally invalidates any pre-existing raw-id cookies — logged-in users
will just need to log in again once.
"""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

_SALT = "creator-session"

_serializer = URLSafeTimedSerializer(settings.session_secret, salt=_SALT)


def create_session_token(creator_id: int) -> str:
    return _serializer.dumps({"creator_id": creator_id})


def read_session_token(token: str) -> int | None:
    try:
        data = _serializer.loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    creator_id = data.get("creator_id") if isinstance(data, dict) else None
    return creator_id if isinstance(creator_id, int) else None
