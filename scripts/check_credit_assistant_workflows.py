"""四组真实正文样例与假模型工具循环，使用临时数据库，禁止接触开发库。"""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


async def main():
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import Session
    from app.db.models import Base, EnterpriseRow, ApplicationRow, ReviewRow
    from app.db.session import get_engine
    from app.repositories.sql_business import ApplicationRepository, ReviewRepository
    from app.repositories.sql_documents import SQLDocumentStore
    from app.services.reviews import ReviewService
    from app.observability.assistant_audit import events, AuditStore
    from app.tools.assistant_tools import ToolExecutor
    from app.agents.credit_assistant import run_turn
    from app.agents.assistant_result import build_result
    from app.agents.context import RequestContext
    from app.schemas.materials import CheckRequest
    from app.services.prechecks import check_materials, check_risks
    from app.api.dependencies import repository

    manifest = json.loads((ROOT / 'fixtures/fictional_applications/manifest.json').read_text(encoding='utf-8'))
    chosen = [case for case in manifest if case['scenario'] in ('normal_1', 'missing_quote', 'invalid_quote', 'amount_difference')]
    assert len(chosen) == 4
    with tempfile.TemporaryDirectory() as directory:
        test_url = os.getenv('CREDIT_ASSISTANT_TEST_URL')
        if test_url:
            from sqlalchemy.engine import make_url
            parsed = make_url(test_url)
            if parsed.get_backend_name() != 'mysql' or not (parsed.database or '').startswith('credit_test_'):
                raise RuntimeError('Refuse non-isolated MySQL database')
        os.environ.update(DATABASE_URL=test_url or 'sqlite:///' + str(Path(directory) / 'isolated.db'),
                          CREDIT_TEST_DATABASE='1', CREDIT_DOCUMENT_ROOT=str(Path(directory) / 'files'))
        get_engine.cache_clear()
        engine = get_engine()
        try:
            Base.metadata.create_all(engine)
            events.create(engine)
            with Session(engine) as session, session.begin():
                for item in chosen:
                    e, a = item['enterprise'], item['application']
                    session.add(EnterpriseRow(id=e['enterprise_id'], payload=e))
                    session.flush()
                    session.add(ApplicationRow(id=a['application_id'], enterprise_id=e['enterprise_id'],
                        status=a['status'], submitted_at=a['submitted_at'], payload=a))
                    session.flush()
            store = SQLDocumentStore()
            for case in chosen:
                for item in case['files']:
                    file = ROOT / item['file']
                    store.upload(case['application_id'], item['category'], file.name, file.read_bytes())
            service = ReviewService(ApplicationRepository(), ReviewRepository())
            executor = ToolExecutor(service, AuditStore(engine))
            conditions = {'is_used_equipment': {'value': False, 'source': 'manual_demo', 'location': '教学条件'}}
            class FakeModel:
                def __init__(self, identifier): self.identifier, self.steps = identifier, 0
                async def complete(self, messages, tools):
                    self.steps += 1
                    if self.steps == 1:
                        return {'tool_calls': [{'id': 'one', 'type': 'function', 'function': {'name': 'get_material_check', 'arguments': json.dumps({'application_id': self.identifier})}}]}
                    return {'content': 'ignored unverified output'}
            async def emit(name, payload): pass
            with Session(engine) as session:
                before = [(x.id, x.status) for x in session.scalars(select(ApplicationRow).order_by(ApplicationRow.id))]
            for case in chosen:
                app_id = case['application_id']
                ctx = RequestContext('test-manager', 'customer_manager', frozenset({app_id}), 'conv', app_id, 'run')
                detail = service.get_application(app_id)
                options = CheckRequest.model_validate({'use_model': False, 'conditions': conditions})
                material = check_materials(detail, options)
                risk = check_risks(detail, options)
                repository.save_material_check(app_id, 'test-enterprise', repository.material_signature(app_id), detail.application.condition_facts, material)
                answer, results = await run_turn('check', ctx, executor, FakeModel(app_id), [], emit, conditions)
                assert len(results) == 1 and results[0][1]['status'] == 'ok'
                structured = build_result(ctx.run_id, app_id, results, store.list(app_id))
                assert structured.application_id == app_id and structured.need_human_review
                assert risk['need_human_review'] is True
                if case['scenario'] == 'normal_1': assert not material['missing_items'] and not material['abnormal_items']
                if case['scenario'] == 'missing_quote': assert any(i['code'] == 'M-E02' for i in material['missing_items'])
                if case['scenario'] == 'invalid_quote': assert any(i['kind'] == 'unreadable' for i in material['abnormal_items'])
                if case['scenario'] == 'amount_difference':
                    assert any(i['category'] == 'amount_review' for i in risk['risk_items'])
                    matches = [i for i in risk['risk_items'] if i['category'] == 'amount_review']
                    assert len(matches) == 1 and len(matches[0]['evidence']) == 2
                    assert {x['quote'] for x in matches[0]['evidence']} == {'120000', '150000'}
                assert 'ignored unverified output' not in answer
                print(case['scenario'], 'verified')
            with Session(engine) as session:
                after = [(x.id, x.status) for x in session.scalars(select(ApplicationRow).order_by(ApplicationRow.id))]
                assert before == after and session.scalar(select(func.count()).select_from(ReviewRow)) == 0
                assert session.execute(select(func.count()).select_from(events)).scalar_one() == 4
        finally:
            engine.dispose()
            get_engine.cache_clear()


if __name__ == '__main__':
    asyncio.run(main())
