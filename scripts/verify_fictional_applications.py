"""只读调用真实业务库的双Workflow；不调用外部模型。"""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

import httpx
from app.main import app


def evaluate(case, material, risk):
    scenario = case['scenario']
    missing = {(item['code'], item['kind']) for item in material['missing_items']}
    abnormal = {(item['code'], item['kind'], item['field']) for item in material['abnormal_items']}
    categories = {item['category'] for item in risk['risk_items']}
    missing_text = ' '.join(item.get('message', '') for item in risk['missing_info'])
    checks = {'human_review': risk['need_human_review'] is True,
              'model_disabled': risk['model_status'] == 'disabled'}
    if scenario.startswith('normal'):
        checks['material_clean'] = not missing and not abnormal
        checks['risk_no_factual_difference'] = not ({'amount_review', 'subject_review'} & categories)
    elif scenario == 'missing_quote':
        checks['missing_price_basis'] = ('M-E02', 'missing') in missing
    elif scenario == 'missing_registration':
        checks['missing_registration'] = ('M-C02', 'missing') in missing
    elif scenario == 'amount_difference':
        checks['amount_review'] = 'amount_review' in categories
    elif scenario == 'name_difference':
        checks['subject_review'] = 'subject_review' in categories
    elif scenario == 'missing_price':
        checks['missing_price_field'] = ('D-QUOTE', 'field_missing', '价格') in abnormal
    elif scenario == 'missing_tax':
        checks['tax_basis_gap'] = '含税口径' in missing_text
        checks['no_invalid_comparison'] = 'amount_review' not in categories
    elif scenario == 'invalid_quote':
        checks['unreadable'] = ('D-QUOTE', 'unreadable', None) in abnormal
    elif scenario == 'missing_plan':
        checks['missing_plan'] = ('M-E01', 'missing') in missing
    else:
        checks['known_scenario'] = False
    return checks


async def main():
    manifest = json.loads((ROOT / 'fixtures/fictional_applications/manifest.json').read_text(encoding='utf-8'))
    options = {'use_model': False, 'conditions': {'is_used_equipment': {
        'value': False, 'source': 'manual_demo', 'location': '设备采购计划写明全新设备'}}}
    output = []
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', timeout=60) as client:
            for case in manifest:
                base = '/api/applications/' + case['application_id']
                detail = await client.get(base)
                files = await client.get(base + '/documents')
                material = await client.post(base + '/materials/check', json=options)
                risk = await client.post(base + '/risk-precheck', json=options)
                item = {'application_id': case['application_id'], 'scenario': case['scenario'],
                    'http': [detail.status_code, files.status_code, material.status_code, risk.status_code]}
                if item['http'] == [200, 200, 200, 200]:
                    item.update(document_count=len(files.json()), material=material.json(), risk=risk.json())
                    item['checks'] = evaluate(case, item['material'], item['risk'])
                else:
                    item['error'] = '至少一个API返回非200，见http字段。'
                    item['responses'] = {'detail': detail.json(), 'documents': files.json(),
                        'materials': material.json(), 'risk': risk.json()}
                output.append(item)
                print(item['application_id'], item['scenario'], 'http=', item['http'],
                    'materials=', item.get('material', {}).get('run_status'),
                    'risk=', item.get('risk', {}).get('run_status'), 'checks=', item.get('checks'))
    target = ROOT / 'fixtures/fictional_applications/workflow-results.json'
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if len(output) != 10 or any(item['http'] != [200, 200, 200, 200] or not all(item['checks'].values()) for item in output):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
