"""结构化最终结果和证据边界的隔离检查；不连接开发库或模型。"""
import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from pydantic import ValidationError
from app.agents.assistant_result import build_result
from app.schemas.assistant import AssistantResponse


def doc(identifier='D1', application='APP-1', value='120000'):
    return {'id': identifier, 'version': 1, 'application_id': application,
            'parsed': {'sections': [{'location': '段落1', 'text': '总价：' + value}]}}


def risk(evidence, application='APP-1'):
    return ('run_risk_precheck', {'status': 'ok', 'application_id': application, 'workflow': {
        'application_id': application, 'run_status': 'completed', 'limitations': [], 'missing_info': [],
        'risk_items': [{'category': 'amount_review', 'origin': 'rule', 'description': '金额不同',
                        'evidence': evidence, 'suggested_human_action': '人工核对', 'policy_ref': None}]}})


def ref(identifier, value):
    return {'material_id': identifier, 'version_no': 1, 'location': '段落1', 'quote': value}


class ResultTests(unittest.TestCase):
    def test_valid_two_sided_evidence(self):
        result = build_result('run', 'APP-1', [risk([ref('D1', '120000'), ref('D2', '150000')])],
            [doc(), doc('D2', value='150000')])
        self.assertEqual(len(result.risk_items[0].evidence), 2)
        self.assertTrue(result.need_human_review)
        self.assertEqual(result.status, 'needs_review')

    def test_cross_application_and_fake_quote_removed(self):
        for documents, evidence in [([doc(application='APP-2'), doc('D2', value='150000')], [ref('D1', '120000'), ref('D2', '150000')]),
                                    ([doc(), doc('D2', value='150000')], [ref('D1', '999999'), ref('D2', '150000')]),
                                    ([doc()], [ref('D1', '120000')])]:
            result = build_result('run', 'APP-1', [risk(evidence)], documents)
            self.assertEqual(result.risk_items, [])
            self.assertTrue(result.missing_info)

    def test_cross_application_result_rejected(self):
        with self.assertRaises(ValueError):
            build_result('run', 'APP-1', [risk([], application='APP-2')])

    def test_extra_final_decision_rejected(self):
        data = build_result('run', None, []).model_dump()
        data['final_credit_decision'] = 'approved'
        with self.assertRaises(ValidationError):
            AssistantResponse.model_validate(data)

    def test_dependency_failure_and_empty_question(self):
        result = build_result('run', 'APP-1', [('search_policy', {'status': 'dependency_unavailable', 'message': '不可用'})])
        self.assertEqual(result.status, 'dependency_unavailable')
        self.assertEqual(result.policy_sources, [])
        self.assertEqual(build_result('run', None, []).status, 'needs_clarification')

    def test_false_policy_source_removed(self):
        source = {'chunk_id': 'fake', 'source_id': 'S1', 'document_id': 'CC-POL-999', 'version': '1.0',
                  'clause': '第一条', 'source_path': 'fake', 'source_line': 1, 'text': 'invented'}
        result = build_result('run', 'APP-1', [('search_policy', {'status': 'ok', 'sources': [source]})])
        self.assertEqual(result.policy_sources, [])
        self.assertTrue(result.missing_info)

    def test_current_policy_source_preserved(self):
        from app.rag.knowledge import load_config, load_chunks
        chunk = load_chunks(load_config())[0][0]
        meta = chunk.metadata
        source = {'chunk_id': chunk.id, 'source_id': 'S1', 'text': chunk.text,
                  **{key: meta[key] for key in ('document_id', 'version', 'clause', 'source_path', 'source_line')}}
        result = build_result('run', 'APP-1', [('search_policy', {'status': 'ok', 'sources': [source]})])
        self.assertEqual(result.policy_sources[0].document_id, meta['document_id'])

    def test_fake_material_issue_removed(self):
        workflow = {'application_id': 'APP-1', 'run_status': 'completed', 'missing_items': [], 'pending_items': [],
                    'abnormal_items': [{'code': 'D', 'message': 'issue', 'material_id': 'wrong', 'version_no': 1}]}
        result = build_result('run', 'APP-1', [('check_materials', {'status': 'ok', 'application_id': 'APP-1', 'workflow': workflow})], [doc()])
        self.assertEqual(result.material_issues, [])
        self.assertTrue(result.missing_info)

    def test_sse_result_and_replay_run_id(self):
        async def check():
            import httpx
            from app.main import app
            from app.api.credit_assistant import sessions
            from app.core.authentication import Principal
            principal = Principal('actor-a', 'customer_manager', 'Manager')
            with patch('app.api.auth.require_principal', return_value=principal), \
                 patch('app.api.credit_assistant.allowed_application_ids', return_value=frozenset({'APP-FICT-001'})):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    cid = (await client.post('/api/credit-assistant/conversations')).json()['conversation_id']
                    path = '/api/credit-assistant/conversations/' + cid + '/messages/stream'
                    payload = {'question': 'hello', 'request_id': 'result-test-001'}
                    first = await client.post(path, json=payload)
                    second = await client.post(path, json=payload)
                    self.assertIn('event: result', first.text)
                    self.assertIn('event: done', first.text)
                    import json
                    def result(text):
                        frame = next(x for x in text.split('\n\n') if x.startswith('event: result'))
                        return json.loads(frame.split('data: ', 1)[1])['result']
                    self.assertEqual(result(first.text), result(second.text))
                    sessions.pop(cid, None)
        asyncio.run(check())

    def test_sse_degraded_and_failed_are_not_successful_complete(self):
        async def check():
            import httpx
            from app.main import app
            from app.api.credit_assistant import sessions
            from app.llm.deepseek import GenerationError
            async def degraded(*args, **kwargs):
                return 'unused', [('search_policy', {'status': 'dependency_unavailable', 'message': 'unavailable'})]
            async def failed(*args, **kwargs):
                raise GenerationError('timeout', 'timeout')
            from app.core.authentication import Principal
            principal = Principal('actor-a', 'customer_manager', 'Manager')
            with patch('app.api.auth.require_principal', return_value=principal), \
                 patch('app.api.credit_assistant.current_principal', return_value=principal), \
                 patch('app.api.credit_assistant.can_access_application', return_value=True), \
                 patch('app.api.credit_assistant.allowed_application_ids', return_value=frozenset({'APP-FICT-001'})):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    cid = (await client.post('/api/credit-assistant/conversations')).json()['conversation_id']
                    path = '/api/credit-assistant/conversations/' + cid + '/messages/stream'
                    with patch('app.api.credit_assistant.ToolExecutor', return_value=object()), patch('app.api.credit_assistant.run_turn', degraded):
                        response = await client.post(path, json={'question': 'test', 'request_id': 'result-test-002', 'application_id': 'APP-FICT-001'})
                    self.assertIn('"status": "dependency_unavailable"', response.text)
                    self.assertIn('"status": "partial"', response.text)
                    with patch('app.api.credit_assistant.ToolExecutor', return_value=object()), patch('app.api.credit_assistant.run_turn', failed):
                        response = await client.post(path, json={'question': 'test', 'request_id': 'result-test-003', 'application_id': 'APP-FICT-001'})
                    self.assertIn('event: error', response.text)
                    self.assertNotIn('event: result', response.text)
                    self.assertNotIn('event: done', response.text)
                    sessions.pop(cid, None)
        asyncio.run(check())


if __name__ == '__main__':
    unittest.main(verbosity=2)
