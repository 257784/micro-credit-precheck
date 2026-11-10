"""在临时内存数据库验证登录、申请归属和对话隔离基础。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.api.auth as auth_api
import app.core.authentication as authentication
import app.core.authorization as authorization
import app.repositories.sql_business as business
from app.agents.memory import ConversationStore, MessageRequest, SessionError
from app.db.auth_models import UserRow
from app.db.models import Base
from app.schemas.business import ApplicationSubmission
from app.services.submissions import submit_application


def main():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    auth_api.get_engine = authentication.get_engine = authorization.get_engine = business.get_engine = lambda: engine
    with Session(engine) as session, session.begin():
        for user_id in ('user1', 'user2'):
            session.add(UserRow(**{'id': user_id, 'username': user_id, 'role': 'enterprise',
                'display_name': user_id, 'password_hash': authentication.hash_password('temporary-demo-credential'), 'active': True}))
    app = FastAPI()
    app.include_router(auth_api.router)
    client = TestClient(app)
    assert client.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/login', json={'username': 'user1', 'credential': 'incorrect'}).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'user1', 'credential': 'temporary-demo-credential'}).status_code == 200
    principal = authentication.current_principal(client.cookies.get(auth_api.COOKIE_NAME))
    assert principal.user_id == 'user1'
    payload = ApplicationSubmission(enterprise_name='教学企业', industry='教学行业', registered_region='教学地区',
        product_type='设备更新贷（教学产品）', requested_amount=100, purpose='教学设备')
    application = submit_application(business.ApplicationRepository(), payload, owner_id=principal.user_id)
    assert authorization.can_access_application(principal, application.application_id)
    other = authentication.Principal('user2', 'enterprise', 'user2')
    assert not authorization.can_access_application(other, application.application_id)
    store = ConversationStore()
    cid = store.create('user1')['conversation_id']
    for call in (lambda: store.get(cid, 'user2'), lambda: store.delete(cid, 'user2'),
                 lambda: store.begin(cid, MessageRequest(question='test', request_id='12345678'), 'user2')):
        try:
            call()
        except SessionError as error:
            assert error.status == 404
        else:
            raise AssertionError('cross-user conversation access allowed')
    assert client.post('/api/auth/logout').status_code == 204
    assert client.get('/api/auth/me').status_code == 401
    engine.dispose()
    print('认证基础隔离验证通过；不代表真实业务路由已接入。')


if __name__ == '__main__':
    main()
