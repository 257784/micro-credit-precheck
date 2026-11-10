"""补充政策无命中、AI 字段缺失、依赖故障与脱敏边界的隔离测试。"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.core.redaction import redact_text
from app.llm.deepseek import GenerationError
from app.schemas.policy import QuestionRequest
from app.services.policy import PolicyQA


def source():
    return {'id': 'C1', 'text': '教学条款仅供人工核验。', 'cosine_distance': 0.1,
            'metadata': {'document_id': 'CC-POL-002', 'version': '1.0', 'clause': '第一条',
                         'title': '教学政策', 'source_path': 'fictional.md', 'source_line': 1}}


class AcceptanceExtra(unittest.TestCase):
    def setUp(self):
        self.request = QuestionRequest(question='测试设备政策', product='equipment')

    def test_no_hit_without_model_configuration(self):
        factory = Mock(side_effect=GenerationError('missing_api_key', 'not configured'))
        result = PolicyQA(retriever=lambda *_: [], client_factory=factory).answer(self.request)
        self.assertEqual(result.status, 'insufficient_evidence')
        factory.assert_not_called()

    def test_missing_ai_field_rejected(self):
        client = SimpleNamespace(settings=SimpleNamespace(model='mock'),
            complete=lambda *_: json.dumps({'status': 'answered', 'statements': [{'text': '缺少引用字段'}]}))
        result = PolicyQA(retriever=lambda *_: [source()], client_factory=lambda: client).answer(self.request)
        self.assertEqual((result.status, result.error_code), ('generation_error', 'invalid_answer'))
        self.assertFalse(result.statements)

    def test_retrieval_failure_is_not_empty_result(self):
        def unavailable(*_):
            raise RuntimeError('simulated outage')
        result = PolicyQA(retriever=unavailable, client_factory=lambda: None).answer(self.request)
        self.assertEqual((result.status, result.error_code), ('retrieval_error', 'retrieval_failed'))

    def test_spaced_phone_currently_not_masked(self):
        sample = '手机号 138 0013 8000'
        self.assertEqual(redact_text(sample, 'model'), sample)

    def test_unknown_document_refused(self):
        factory = Mock()
        result = PolicyQA(retriever=lambda *_: [source()], client_factory=factory).answer(
            QuestionRequest(question='请解释 CC-POL-999', product='equipment'))
        self.assertEqual(result.status, 'insufficient_evidence')
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
