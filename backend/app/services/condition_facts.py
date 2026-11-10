"""条件事实的声明复用、材料候选与冲突处理；候选不能自动免交材料。"""
from app.schemas.materials import Conditions, Fact

FIELDS = {
    'is_used_equipment': {'是否二手设备', '设备是否为二手', '设备新旧', '设备新旧情况'},
    'uses_order_contract': {'是否以具体订单或合同作为用途依据', '是否以具体订单或合同为用途依据'},
}
YES = {'是', '二手', '二手设备', '是二手', '以具体订单或合同为依据'}
NO = {'否', '全新', '新设备', '全新设备', '不是二手', '不以具体订单或合同为依据'}


def resolve_conditions(detail, requested):
    from app.services.documents import DocumentService
    docs = DocumentService().list(detail.application.application_id)
    latest = {}
    for doc in docs:
        if doc.get('application_id') != detail.application.application_id:
            continue
        category = doc.get('category')
        if category not in latest or doc['version'] > latest[category]['version']:
            latest[category] = doc
    candidates = []
    for doc in latest.values():
        parsed = doc.get('parsed', {})
        if parsed.get('status') != 'parsed':
            continue
        for name, field in parsed.get('fields', {}).items():
            if not isinstance(field, dict):
                continue
            raw = field.get('value')
            if not isinstance(raw, str):
                continue
            value = raw.strip()
            location = field.get('location')
            quote = next((line for section in parsed.get('sections', []) if section.get('location') == location
                for line in section.get('text', '').splitlines()
                if line.partition('：')[0].strip() == name and line.partition('：')[2].strip() == value), None)
            if quote is None:
                continue
            for condition, labels in FIELDS.items():
                if name in labels and value in YES | NO:
                    candidates.append({'condition': condition, 'value': value in YES, 'quote': quote,
                        'material_id': doc['id'], 'version': doc['version'], 'location': location})
    confirmed = detail.application.condition_facts or {}
    resolved, conflicts = {}, []
    for key in FIELDS:
        saved = confirmed.get(key)
        provided = getattr(requested, key, None)
        try:
            stored = Fact(value=saved['value'], source='application_field', location=saved.get('location') or '企业申请声明') if saved else None
        except (KeyError, TypeError, ValueError):
            stored = None
        if stored and provided and provided.value is not None and stored.value != provided.value:
            conflicts.append(key)
            continue
        chosen = stored or provided
        if chosen and chosen.value is not None and any(c['condition'] == key and c['value'] != chosen.value for c in candidates):
            conflicts.append(key)
            continue
        if chosen:
            resolved[key] = chosen
    return Conditions(**resolved), candidates, conflicts
