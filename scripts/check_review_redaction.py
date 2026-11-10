"""使用虚构号码验证三种复核选择和不同场景脱敏。"""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import httpx
from app.core.redaction import redact_text, redact_value
from app.llm.deepseek import DeepSeekClient, Settings
from app.llm.streaming import AsyncDeepSeek
from app.llm.tool_client import ToolClient
from app.schemas.business import ReviewSubmission
from app.services.reviews import ReviewInputError, ReviewService

PHONE = '13800138000'
IDENTITY = '11010519491231002X'


def check_review():
    report = SimpleNamespace(report_id='R1', generated_at='2026-01-01T00:00:00+00:00',
        workflow_result={}, analysis_status='needs_human_review', items=[SimpleNamespace(item_id=x) for x in 'abc'])
    detail = SimpleNamespace(application=SimpleNamespace(status='风控复核中'), reports=[report])
    repository, store = Mock(), Mock()
    repository.get_application.return_value = detail
    service = ReviewService(repository, store)
    service.get_application = Mock(return_value=detail)
    entries = [{'item_id': 'a', 'decision': 'accepted'}, {'item_id': 'b', 'decision': 'partial', 'correction_note': '修改范围'},
               {'item_id': 'c', 'decision': 'rejected', 'correction_note': '依据不足'}]
    body = ReviewSubmission(review_result='complete', overall_adoption='partial', review_note='人工检查', report_id='R1', item_reviews=entries)
    service.submit('APP', 'RISK', body)
    assert [x.decision for x in store.append.call_args.args[-2]] == ['accepted', 'partial', 'rejected']
    assert store.append.call_args.args[-1] == 'partial'
    try:
        service.submit('APP', 'RISK', ReviewSubmission(review_result='complete', review_note='人工检查', report_id='R1', item_reviews=entries))
    except ReviewInputError:
        pass
    else:
        raise AssertionError('完成复核必须选择总体处理方式')
    for decision in ('partial', 'rejected'):
        missing = [dict(x) for x in entries]
        missing[1] = {'item_id': 'b', 'decision': decision}
        try:
            service.submit('APP', 'RISK', ReviewSubmission(review_result='complete', overall_adoption='accepted', review_note='人工检查', report_id='R1', item_reviews=missing))
        except ReviewInputError:
            pass
        else:
            raise AssertionError('部分采纳和不采纳必须提供说明')
    assert ReviewSubmission(review_result='complete', review_note='旧记录', item_reviews=[{'item_id': 'a', 'decision': 'confirmed'}]).item_reviews[0].decision == 'confirmed'


async def check_model():
    seen = []
    async def handler(request):
        data = json.loads(request.content)
        seen.append(json.dumps(data, ensure_ascii=False))
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    transport = httpx.MockTransport(handler)
    client = AsyncDeepSeek(Settings('fake-test-token', 'test', 10), transport=transport)
    message = [{'role': 'user', 'content': '电话：' + PHONE + ' 身份证：' + IDENTITY}]
    await client.complete(message)
    factory = httpx.AsyncClient
    with patch('app.llm.tool_client.Settings.from_environment', return_value=Settings('fake-test-token', 'test', 10)), \
         patch('app.llm.tool_client.httpx.AsyncClient', side_effect=lambda **kwargs: factory(transport=transport, **kwargs)):
        await ToolClient().complete(message, [])
    assert len(seen) == 2 and all(PHONE not in entry and IDENTITY not in entry for entry in seen)
    assert all('[手机号已隐藏]' in entry and '[身份证号已隐藏]' in entry for entry in seen)


def main():
    text = '手机号：' + PHONE + ' 身份证：' + IDENTITY
    masked = redact_text(text)
    assert PHONE not in masked and IDENTITY not in masked and '138****8000' in masked and '110105********002X' in masked
    result = redact_value({'application_id': 'APP-1', 'parsed': {'text': text}})
    assert result['application_id'] == 'APP-1' and PHONE not in result['parsed']['text']
    assert redact_text('金额120000元，材料编号M-E01') == '金额120000元，材料编号M-E01'
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}).encode()
    opener = Mock()
    opener.open.return_value = response
    with patch('app.llm.deepseek.build_opener', return_value=opener):
        DeepSeekClient(Settings('fake-test-token', 'test', 10)).complete([{'role': 'user', 'content': text}])
    sent = opener.open.call_args.args[0].data.decode()
    assert PHONE not in sent and IDENTITY not in sent and '[手机号已隐藏]' in sent
    check_review()
    asyncio.run(check_model())
    print('三种人工复核、历史兼容、页面及模型输入脱敏验证通过。')


if __name__ == '__main__':
    main()
