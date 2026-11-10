"""使用隔离 SQLite 验证角色边界、检查记录、分配和审批。"""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.models import Base, ApplicationRow, MaterialRow
from app.db.auth_models import UserRow
import app.api.auth as api
import app.core.authentication as auth
import app.core.authorization as authorization
import app.repositories.sql_business as business
import app.repositories.sql_documents as documents
import app.observability.operation_audit as operation_audit
import app.api.operation_audit as operation_audit_api
from app.main import app


def main():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    api.get_engine = auth.get_engine = authorization.get_engine = business.get_engine = documents.get_engine = operation_audit.get_engine = operation_audit_api.get_engine = lambda: engine
    roles = {'e1': 'enterprise', 'e2': 'enterprise', 'm1': 'customer_manager', 'm2': 'customer_manager',
             'r': 'risk_reviewer', 'p': 'approver', 'admin': 'admin'}
    with Session(engine) as session, session.begin():
        for name, role in roles.items():
            session.add(UserRow(id=name, username=name, display_name=name, role=role,
                                password_hash=auth.hash_password('test-password-123'), active=True))
    clients = {name: TestClient(app) for name in roles}
    for name, client in clients.items():
        assert client.post('/api/auth/login', json={'username': name, 'credential': 'test-password-123'}).status_code == 200
    payload = {'enterprise_name': '虚构企业', 'industry': '教学', 'registered_region': '教学',
               'product_type': '设备更新贷（教学产品）', 'requested_amount': 100, 'purpose': '教学', 'is_used_equipment': False}
    ids = []
    result = {'application_id': '', 'run_status': 'completed', 'missing_items': [], 'abnormal_items': [], 'pending_items': []}
    for i in range(2):
        response = clients['e1'].post('/api/applications', json=payload)
        assert response.status_code == 201 and response.json()['status'] == '草稿', response.text
        identifier = response.json()['application_id']; ids.append(identifier)
        assert clients['e2'].get('/api/applications/' + identifier).status_code == 404
        assert clients['e1'].get('/api/applications/' + identifier).status_code == 200
        assert clients['m1'].post('/api/applications/' + identifier + '/claim').status_code == 403
        blocked = {**result, 'application_id': identifier, 'missing_items': [{'message': '缺少材料'}]}
        with patch('app.services.prechecks.check_materials', return_value=blocked):
            assert clients['e1'].post('/api/applications/' + identifier + '/resubmit', json={}).status_code == 422
        with patch('app.services.prechecks.check_materials', return_value={**result, 'application_id': identifier}):
            assert clients['e1'].post('/api/applications/' + identifier + '/materials/check', json={}).status_code == 200
            assert clients['e1'].post('/api/applications/' + identifier + '/resubmit', json={}).status_code == 200
    with Session(engine) as session:
        assert {session.get(ApplicationRow, id).payload['account_manager_id'] for id in ids} == {'m1', 'm2'}
    assert clients['admin'].patch('/api/auth/users/m1', json={'active': False}).status_code == 409
    assert clients['admin'].patch('/api/auth/users/admin', json={'active': False}).status_code == 409
    assert clients['e1'].post('/api/auth/users', json={'username': 'new', 'display_name': 'new',
        'role': 'approver', 'credential': 'test-password-123'}).status_code == 403
    created = clients['admin'].post('/api/auth/users', json={'username': 'new', 'display_name': 'new',
        'role': 'approver', 'credential': 'test-password-123'})
    assert created.status_code == 201
    assert clients['admin'].patch('/api/auth/users/' + created.json()['user_id'], json={'active': False}).status_code == 200
    identifier = ids[0]
    assert clients['m1'].post('/api/applications/' + identifier + '/materials/check', json={}).status_code == 403
    assert clients['m1'].post('/api/applications/' + identifier + '/risk-precheck', json={}).status_code == 403
    assert clients['m1'].post('/api/applications/' + identifier + '/supplement-suggestion', json={'note': '请补充信息'}).status_code == 200
    with Session(engine) as session, session.begin():
        row = session.get(ApplicationRow, identifier)
        assert row.status == '待风控复核'
        session.add(MaterialRow(id='new', application_id=identifier, category='x', version=1, source='upload', payload={}))
    assert clients['e1'].get('/api/applications/' + identifier + '/material-checks').json()[0]['stale'] is True
    assert clients['p'].get('/api/applications/' + identifier).status_code == 404
    with Session(engine) as session, session.begin():
        session.get(ApplicationRow, identifier).status = '待审批'
    assert clients['p'].get('/api/applications/' + identifier).status_code == 200
    assert clients['m1'].post('/api/applications/' + identifier + '/approval/start').status_code == 403
    assert clients['p'].post('/api/applications/' + identifier + '/approval/start').status_code == 200
    assert clients['p'].post('/api/applications/' + identifier + '/approval/approve', json={'note': '人工确认'}).status_code == 200
    assert clients['p'].post('/api/applications/' + identifier + '/approval/reject', json={'note': '重复'}).status_code == 409
    assert clients['p'].get('/api/applications/' + identifier + '/approval-records').json()[-1]['action'] == 'approve'
    audit = clients['admin'].get('/api/operation-audit', params={'application_id': identifier})
    assert audit.status_code == 200
    assert any(e['action'] == 'approve' and e['actor_id'] == 'p' and e['after']['status'] == '审批通过' for e in audit.json())
    assert '人工确认' not in audit.text and '请补充信息' not in audit.text
    assert clients['admin'].post('/api/policy/conversations').status_code == 403
    with Session(engine) as session, session.begin():
        session.get(UserRow, 'm1').active = False
        session.get(UserRow, 'm2').active = False
    pending = clients['e1'].post('/api/applications', json=payload).json()['application_id']
    with patch('app.services.prechecks.check_materials', return_value={**result, 'application_id': pending}):
        assert clients['e1'].post('/api/applications/' + pending + '/resubmit', json={}).status_code == 200
    with Session(engine) as session, session.begin():
        assert session.get(ApplicationRow, pending).payload['assignment_pending'] is True
        session.get(UserRow, 'm2').active = True
    assert clients['m2'].post('/api/auth/login', json={'username': 'm2', 'credential': 'test-password-123'}).status_code == 200
    with Session(engine) as session:
        assert session.get(ApplicationRow, pending).payload['account_manager_id'] == 'm2'
    print('隔离测试通过：草稿、材料检查、分配、越权、补件建议、过期和审批。')


if __name__ == '__main__':
    main()
