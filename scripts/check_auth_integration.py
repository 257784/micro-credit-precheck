"""在内存数据库检查应用路由的多用户边界，不连接开发库。"""
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.models import ApplicationRow, Base, EnterpriseRow, MaterialRow
from app.db.auth_models import UserRow
import app.api.auth as api
import app.core.authentication as auth
import app.core.authorization as authorization
import app.repositories.sql_business as business
import app.repositories.sql_documents as documents
import app.observability.assistant_audit as audit_module
import app.observability.operation_audit as operation_audit
import app.api.operation_audit as operation_audit_api
from app.main import app


def main():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    audit_module.events.create(engine)
    api.get_engine = auth.get_engine = authorization.get_engine = business.get_engine = documents.get_engine = audit_module.get_engine = operation_audit.get_engine = operation_audit_api.get_engine = lambda: engine
    accounts = {'e1': 'enterprise', 'e2': 'enterprise', 'm1': 'customer_manager',
                'm2': 'customer_manager', 'r1': 'risk_reviewer', 'admin1': 'admin'}
    with Session(engine) as session, session.begin():
        for user_id, role in accounts.items():
            session.add(UserRow(**{'id': user_id, 'username': user_id, 'role': role,
                'display_name': user_id, 'password_hash': auth.hash_password('temporary-demo-credential'), 'active': True}))
    clients = {u: TestClient(app) for u in accounts}
    assert TestClient(app).get('/api/applications').status_code == 401
    for user_id, client in clients.items():
        assert client.post('/api/auth/login', json={'username': user_id, 'credential': 'temporary-demo-credential'}).status_code == 200
    payload = {'enterprise_name': '虚构企业', 'industry': '教学行业', 'registered_region': '教学地区',
               'product_type': '设备更新贷（教学产品）', 'requested_amount': 100, 'purpose': '教学用途'}
    response = clients['e1'].post('/api/applications', json=payload)
    assert response.status_code == 201
    identifier = response.json()['application_id']
    assert clients['e1'].get('/api/applications').json()[0]['application_id'] == identifier
    assert clients['e2'].get('/api/applications').json() == []
    assert clients['e2'].get(f'/api/applications/{identifier}/documents').status_code == 404
    assert clients['m1'].get('/api/auth/users').status_code == 403
    assert clients['admin1'].get('/api/auth/users').status_code == 200
    assert clients['admin1'].get('/api/credit-assistant/audit').status_code == 200
    assert clients['m1'].get('/api/credit-assistant/audit').status_code == 403
    assert clients['admin1'].post(f'/api/applications/{identifier}/assign', json={'owner_id': 'e2'}).status_code == 403
    assert clients['e2'].post(f'/api/applications/{identifier}/assign', json={'owner_id': 'e2'}).status_code == 403
    assert clients['m1'].get(f'/api/applications/{identifier}').status_code == 404
    assert clients['m1'].get('/api/applications/unassigned').status_code == 403
    assert clients['m1'].post(f'/api/applications/{identifier}/claim').status_code == 403
    assert clients['m2'].post(f'/api/applications/{identifier}/claim').status_code == 403
    assert clients['m2'].get(f'/api/applications/{identifier}').status_code == 404
    assert clients['m1'].post(f'/api/applications/{identifier}/review/start', headers={'X-Demo-Role': 'risk_reviewer'}).status_code == 404
    assert clients['r1'].get(f'/api/applications/{identifier}').status_code == 404
    assert clients['e1'].post(f'/api/applications/{identifier}/resubmit', json={'is_used_equipment': False}).status_code == 422
    with tempfile.TemporaryDirectory() as root, patch.dict('os.environ', {'CREDIT_DOCUMENT_ROOT': root}):
        fixture = Path(__file__).resolve().parents[1] / 'fixtures' / 'fictional_applications' / 'APP-FICT-001'
        bad = clients['e1'].post(f'/api/applications/{identifier}/documents',
            params={'category': 'D-QUOTE', 'filename': 'bad.docx'}, content=b'not a document')
        assert bad.status_code == 200 and bad.json()['parsed']['status'] == 'failed'
        assert clients['e1'].post(f'/api/applications/{identifier}/resubmit', json={'is_used_equipment': False}).status_code == 422
        for category in ('M-C01', 'M-C02', 'M-C03', 'M-E01', 'D-QUOTE', 'D-UNSIGNED'):
            path = next(fixture.glob(category + '-*.docx'))
            response = clients['e1'].post(f'/api/applications/{identifier}/documents',
                params={'category': category, 'filename': path.name}, content=path.read_bytes())
            assert response.status_code == 200, response.text
        response = clients['e1'].post(f'/api/applications/{identifier}/resubmit', json={'is_used_equipment': False})
        assert response.status_code == 200, response.text
        assert response.json()['status'] == '待风控复核'
        assert clients['m1'].get(f'/api/applications/{identifier}').status_code == 200
        assert clients['e1'].post(f'/api/applications/{identifier}/resubmit', json={'is_used_equipment': False}).status_code == 409
        assert clients['r1'].get(f'/api/applications/{identifier}').status_code == 200
        detail_after = clients['r1'].get(f'/api/applications/{identifier}').json()
        assert detail_after['application']['condition_facts']['is_used_equipment']['value'] is False
        options = {'use_model': False}
        material = clients['e1'].post(f'/api/applications/{identifier}/materials/check', json=options)
        assert material.status_code == 200 and material.json()['conditions']['is_used_equipment']['value'] is False
        from app.api.dependencies import repository
        with patch.object(repository, 'save_workflow_report', side_effect=OSError('simulated failure')):
            failed_save = clients['r1'].post(f'/api/applications/{identifier}/risk-precheck', json=options)
        assert failed_save.status_code == 503
        assert clients['r1'].get(f'/api/applications/{identifier}').json()['reports'] == []
        from app.services.prechecks import check_risks
        def changing_material(*args, **kwargs):
            value = check_risks(*args, **kwargs)
            with Session(engine) as session, session.begin():
                session.add(MaterialRow(id='concurrent-material', application_id=identifier,
                    category='concurrent', version=1, source='legacy', payload={}))
            return value
        with patch('app.services.prechecks.check_risks', side_effect=changing_material):
            changed = clients['r1'].post(f'/api/applications/{identifier}/risk-precheck', json=options)
        assert changed.status_code == 409, changed.text
        with Session(engine) as session, session.begin():
            session.delete(session.get(MaterialRow, 'concurrent-material'))
        preview = clients['m1'].post(f'/api/applications/{identifier}/risk-precheck', json=options)
        assert preview.status_code == 403
        degraded_result = {'application_id': identifier, 'run_status': 'degraded', 'risk_items': [],
            'missing_info': [{'message': '依赖不可用'}], 'model_status': 'failed', 'retrieval_status': 'failed',
            'limitations': ['请人工核验'], 'material_snapshot': []}
        with patch('app.services.prechecks.check_risks', return_value=degraded_result):
            degraded = clients['r1'].post(f'/api/applications/{identifier}/risk-precheck', json=options)
        assert degraded.status_code == 200, degraded.text
        failed_report = next(item for item in clients['r1'].get(f'/api/applications/{identifier}').json()['reports']
                             if item['report_id'] == degraded.json()['saved_report_id'])
        assert failed_report['analysis_status'] == 'failed' and failed_report['items']
        first = clients['r1'].post(f'/api/applications/{identifier}/risk-precheck', json=options)
        assert first.status_code == 200, first.text
        assert first.json()['conditions']['is_used_equipment']['value'] is False
        first_id = first.json()['saved_report_id']
        again = clients['r1'].post(f'/api/applications/{identifier}/risk-precheck', json=options)
        assert again.status_code == 200, again.text
        report_id = again.json()['saved_report_id']
        assert first_id != report_id
        detail = clients['r1'].get(f'/api/applications/{identifier}').json()
        report = next(item for item in detail['reports'] if item['report_id'] == report_id)
        assert report['workflow_result']['application_id'] == identifier and report['material_signature']
        assert clients['r1'].post(f'/api/applications/{identifier}/review/start').status_code == 200
        reviews = [{'item_id': item['item_id'], 'decision': 'confirmed'} for item in report['items']]
        payload_review = {'review_result': 'complete', 'review_note': '人工核验完毕', 'item_reviews': reviews, 'report_id': first_id}
        assert clients['r1'].post(f'/api/applications/{identifier}/review/submit', json=payload_review).status_code == 409
        payload_review['report_id'] = report_id
        submitted = clients['r1'].post(f'/api/applications/{identifier}/review/submit', json=payload_review)
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()['application']['status'] == '待审批'
        assert submitted.json()['reviews'][-1]['report_id'] == report_id
        assert clients['m1'].get('/api/operation-audit').status_code == 403
        audit_response = clients['admin1'].get('/api/operation-audit', params={'application_id': identifier})
        assert audit_response.status_code == 200, audit_response.text
        operation_logs = audit_response.json()
        assert any(e['action'] == 'create_draft' and e['actor_id'] == 'e1' for e in operation_logs)
        assert any(e['action'] == 'submit' and e['before']['status'] == '草稿' and e['after']['status'] == '待风控复核' for e in operation_logs if e['result'] == 'success')
        assert any(e['action'] == 'risk_report' and e['actor_id'] == 'r1' and e['result'] == 'degraded' for e in operation_logs)
        assert any(e['action'] == 'risk_report' and e['result'] == 'failed' and e['reason_code'] == 'dependency_failure' for e in operation_logs)
        assert any(e['action'] == 'review_complete' and e['before']['status'] == '风控复核中' and e['after']['status'] == '待审批' for e in operation_logs)
        assert any(e['action'] == 'review_submit' and e['result'] == 'failed' and e['reason_code'] == 'state_conflict' for e in operation_logs)
        assert '人工核验完毕' not in audit_response.text and 'not a document' not in audit_response.text
    assert clients['e1'].post('/api/applications', json=payload, headers={'Origin': 'https://untrusted.invalid'}).status_code == 403
    cid = clients['e1'].post('/api/policy/conversations').json()['conversation_id']
    assert clients['e2'].get(f'/api/policy/conversations/{cid}').status_code == 404
    assert clients['e2'].delete(f'/api/policy/conversations/{cid}').status_code == 404
    cid = clients['m1'].post('/api/credit-assistant/conversations').json()['conversation_id']
    assert clients['m2'].get(f'/api/credit-assistant/conversations/{cid}').status_code == 404
    assert clients['e1'].get(f'/api/credit-assistant/conversations/{cid}').status_code == 403
    assert clients['e1'].post('/api/auth/logout').status_code == 204
    assert clients['e1'].get('/api/applications').status_code == 401
    with Session(engine) as session, session.begin():
        session.get(UserRow, 'e2').active = False
    assert clients['e2'].get('/api/applications').status_code == 401
    engine.dispose()
    print('隔离数据库多用户接口验证通过。')


if __name__ == '__main__':
    main()
