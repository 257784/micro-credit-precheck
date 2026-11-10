"""教学账号登录：服务端验证密码并管理可撤销的短期会话。"""
import os
from threading import RLock
from time import monotonic
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.authentication import current_principal, hash_password, issue_session, token_digest, verify_password
from app.db.auth_models import LoginSessionRow, UserRow
from app.db.auth_models import ApplicationOwnerRow
from app.db.models import ApplicationRow
from uuid import uuid4
from app.db.session import get_engine

router = APIRouter(prefix='/api/auth')
COOKIE_NAME = 'credit_session'
_attempts = {}
_attempt_lock = RLock()
_dummy_hash = hash_password('non-account-placeholder')


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=100)
    credential: str = Field(min_length=1, max_length=256)


class NewUser(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    username: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    role: str
    credential: str = Field(min_length=12, max_length=256)


class UserChanges(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str | None = None
    active: bool | None = Field(default=None, strict=True)


ROLES = ('enterprise', 'customer_manager', 'risk_reviewer', 'approver', 'admin')


@router.post('/users', status_code=201)
def create_user(body: NewUser, request: Request):
    if request.state.principal.role != 'admin':
        raise HTTPException(403, '仅管理员可以创建账号。')
    if body.role not in ROLES:
        raise HTTPException(422, '无效角色。')
    with Session(get_engine()) as session, session.begin():
        if session.scalar(select(UserRow.id).where(UserRow.username == body.username)):
            raise HTTPException(409, '账号已存在。')
        user = UserRow(id=uuid4().hex, username=body.username, display_name=body.display_name,
                       role=body.role, password_hash=hash_password(body.credential), active=True)
        session.add(user)
        return {'user_id': user.id, 'role': user.role, 'display_name': user.display_name}


@router.patch('/users/{user_id}')
def update_user(user_id: str, body: UserChanges, request: Request):
    principal = request.state.principal
    if principal.role != 'admin':
        raise HTTPException(403, '仅管理员可以管理账号。')
    if user_id == principal.user_id:
        raise HTTPException(409, '不能修改当前登录的管理员账号。')
    if body.role is not None and body.role not in ROLES:
        raise HTTPException(422, '无效角色。')
    with Session(get_engine()) as session, session.begin():
        user = session.scalar(select(UserRow).where(UserRow.id == user_id).with_for_update())
        if user is None:
            raise HTTPException(404, '账号不存在。')
        changing_role = body.role is not None and body.role != user.role
        if changing_role and user.role == 'enterprise' and session.scalar(select(ApplicationOwnerRow.application_id).where(
            ApplicationOwnerRow.user_id == user_id).limit(1)):
            raise HTTPException(409, '企业账号已有申请归属，不能直接更改角色。')
        if (changing_role or body.active is False) and user.role == 'customer_manager':
            for application in session.scalars(select(ApplicationRow).where(ApplicationRow.status.not_in(
                ('草稿', '审批通过', '审批未通过')))):
                if application.payload.get('account_manager_id') == user_id:
                    raise HTTPException(409, '客户经理仍有未结束申请，不能直接停用或更换角色。')
        if body.role is not None:
            user.role = body.role
        if body.active is not None:
            user.active = body.active
        if changing_role or body.active is False:
            session.execute(delete(LoginSessionRow).where(LoginSessionRow.user_id == user_id))
        return {'user_id': user.id, 'role': user.role, 'active': user.active}


def require_principal(request: Request):
    principal = current_principal(request.cookies.get(COOKIE_NAME))
    if principal is None:
        raise HTTPException(401, '请登录后继续。')
    return principal


@router.post('/login')
def login(body: LoginInput, response: Response, request: Request):
    key = (request.client.host if request.client else 'unknown', body.username.strip().casefold())
    now = monotonic()
    with _attempt_lock:
        for old in list(_attempts):
            _attempts[old] = [stamp for stamp in _attempts[old] if now - stamp < 300]
            if not _attempts[old]:
                del _attempts[old]
        if len(_attempts) >= 10000 and key not in _attempts:
            raise HTTPException(429, '登录请求过多，请稍后重试。')
        if len(_attempts.get(key, [])) >= 5:
            raise HTTPException(429, '登录尝试过多，请五分钟后重试。')
        _attempts.setdefault(key, []).append(now)
    with Session(get_engine()) as session, session.begin():
        user = session.scalar(select(UserRow).where(UserRow.username == body.username.strip()).with_for_update())
        matches = verify_password(body.credential, user.password_hash if user else _dummy_hash)
        if not user or not user.active or not matches:
            raise HTTPException(401, '账号或密码错误。')
        principal = {'user_id': user.id, 'role': user.role, 'display_name': user.display_name}
        token = issue_session(principal['user_id'], session=session)
    if principal['role'] == 'customer_manager':
        from app.api.dependencies import repository
        repository.assign_pending()
    with _attempt_lock:
        _attempts.pop(key, None)
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=os.getenv('CREDIT_COOKIE_SECURE') == '1',
                        samesite='strict', max_age=8 * 60 * 60, path='/')
    return principal


@router.get('/me')
def me(request: Request):
    principal = require_principal(request)
    return {'user_id': principal.user_id, 'role': principal.role, 'display_name': principal.display_name}


@router.get('/users')
def users(request: Request):
    if request.state.principal.role != 'admin':
        raise HTTPException(403, '无权查看账号列表。')
    with Session(get_engine()) as session:
        return [{'user_id': user.id, 'role': user.role, 'display_name': user.display_name, 'active': user.active}
                for user in session.scalars(select(UserRow))]


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response):
    value = request.cookies.get(COOKIE_NAME)
    if value and len(value) <= 128:
        with Session(get_engine()) as session, session.begin():
            session.execute(delete(LoginSessionRow).where(LoginSessionRow.token_hash == token_digest(value)))
    response.delete_cookie(COOKIE_NAME, path='/')
