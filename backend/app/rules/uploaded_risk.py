"""从实际解析字段核对设备申请，禁止使用离线预设答案。"""
from decimal import Decimal, InvalidOperation


def latest_documents(application_id):
    from app.repositories.documents import DocumentStore
    latest = {}
    for item in DocumentStore().list(application_id):
        latest[item['category']] = item
    return latest


def analyze_uploaded(detail):
    documents = latest_documents(detail.application.application_id)
    findings, missing = [], []
    def field(code, key):
        doc = documents.get(code)
        value = doc['parsed']['fields'].get(key) if doc and doc['parsed']['status'] == 'parsed' else None
        if not value:
            missing.append({'message': f'{code}缺少可核对字段：{key}', 'source': 'uploaded_document'})
            return None
        return {'material_id': doc['id'], 'version_no': doc['version'], 'location': value['location'],
                'quote': value['value'], 'source': 'uploaded_document'}
    def add(category, description, evidence, ref):
        findings.append({'item_id': 'uploaded-' + str(len(findings)+1), 'origin': 'rule', 'category': category,
                         'description': description, 'evidence': evidence, 'policy_ref': ref,
                         'suggested_human_action': '核对双方原文与口径，记录解释；不自动作授信决定。'})
    if not documents:
        return None
    a, b = field('M-C01', '主体名称'), field('M-C02', '主体名称')
    if a and b and a['quote'] != b['quote']:
        add('subject_review', '申请与登记主体名称不同，需核对简称或变更关系。', [a,b], ['CC-REV-001','1.0','第二条'])
    if detail.application.product_type == '设备更新贷（教学产品）':
        amount, quote = field('M-E01', '总价'), field('D-QUOTE', '价格')
        comparable = True
        for key in ('币种','金额单位','含税口径','费用构成'):
            left, right = field('M-E01',key), field('D-QUOTE',key)
            if not left or not right or left['quote'] != right['quote']:
                comparable = False
                missing.append({'message': f'计划与报价的{key}未确定一致，不能直接计算差异。'})
        if comparable and amount and quote:
            try:
                a, b = Decimal(amount['quote']), Decimal(quote['quote'])
                if not a.is_finite() or not b.is_finite():
                    raise InvalidOperation
                if a != b:
                    add('amount_review', f'同口径采购计划{a}元与报价{b}元不一致。', [amount,quote], ['CC-POL-002','1.0','第六条'])
            except InvalidOperation:
                missing.append({'message': '金额无法转为有限数值，需人工核对。'})
    else:
        missing.append({'message': '当前上传事实核对仅覆盖设备样例，其他产品需人工核对。'})
    return {'findings': findings, 'missing_info': missing}
