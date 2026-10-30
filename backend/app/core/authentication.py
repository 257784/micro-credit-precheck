"""账户密码及不可逆保存的会话令牌；不依赖客户端自报角色。"""
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.db.auth_models import LoginSessionRow, UserRow
from app.db.session import get_engine


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    display_name: str


def hash_password(password):
    if not 12 <= len(password) <= 256:
        raise ValueError('密码长度必须为 12 至 256 个字符')
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return 'scrypt$' + salt + '$' + digest


def verify_password(password, encoded):
    try:
        algorithm, salt, expected = encoded.split('$')
        if algorithm != 'scrypt' or len(password) > 256:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(user_id):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
    with Session(get_engine()) as session, session.begin():
        session.add(LoginSessionRow(token_hash=token_digest(token), user_id=user_id, expires_at=expires))
    return token


def current_principal(token):
    if not token or len(token) > 128:
        return None
    with Session(get_engine()) as session:
        login = session.get(LoginSessionRow, token_digest(token))
        if not login or login.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            return None
        user = session.get(UserRow, login.user_id)
        if not user or not user.active:
            return None
        return Principal(user.id, user.role, user.display_name)
