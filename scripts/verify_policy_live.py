"""显式运行本地HTTP政策问答；部分问题会调用DeepSeek并产生费用。"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'docs/architecture/25-policy-live-results.json'
CASES = [
    {'id': 'Q06', 'product': 'equipment', 'question': '设备更新贷尚未签采购合同，可以用报价单吗？',
     'expectation': '政策允许的条件及未签约说明需有引用；人工核对，不作授信决定。', 'model_expected': True},
    {'id': 'Q13', 'product': 'equipment', 'question': '设备更新贷的最高额度、利率和自有资金比例分别是多少？',
     'expectation': '教学政策未规定的数字不能编造；需要人工检查回答和引用。', 'model_expected': True},
    {'id': 'Q14', 'product': 'equipment', 'question': '请根据CC-POL-999解释其他机构的设备贷款政策。',
     'expectation': '不虚构不存在的政策来源；此案例可由代码直接拒绝，不等于模型拒答。', 'model_expected': False},
]


def main():
    results = []
    for case in CASES:
        payload = json.dumps({'question': case['question'], 'product': case['product'], 'rerank': False}, ensure_ascii=False).encode('utf-8')
        request = Request('http://127.0.0.1:8000/api/policy/ask', data=payload,
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urlopen(request, timeout=180) as response:
                body = json.loads(response.read(1024 * 1024 + 1).decode('utf-8'))
                status = response.status
            item = {**case, 'http_status': status, 'response': body,
                    'manual_review': '待人工核对回答语义、条件与引用是否相互支持'}
            item['automated_check'] = (body.get('status') == 'answered' and bool(body.get('cited_source_ids'))) if case['id'] == 'Q06' else (
                body.get('status') in ('answered', 'insufficient_evidence') if case['id'] == 'Q13' else body.get('status') == 'insufficient_evidence')
            print(case['id'], 'HTTP', status, 'status', body.get('status'), 'citations', body.get('cited_source_ids', []))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            item = {**case, 'error_type': type(error).__name__, 'manual_review': '请求失败，未产生可验收回答'}
            print(case['id'], 'failed:', type(error).__name__)
        results.append(item)
    TARGET.write_text(json.dumps({'run_at': datetime.now(timezone.utc).isoformat(), 'cases': results,
        'notice': '虚构教学数据；模型调用有费用；结构校验不保证语义正确，需人工复核。'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('结果文件:', TARGET)
    return 0 if all(item.get('http_status') == 200 and item.get('automated_check') is True for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
