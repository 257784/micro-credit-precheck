"""把风险 Workflow 的输出转成可持久化、可人工复核的报告。"""
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.business import EvidenceRef, KnowledgeItem, Report, ReportAspect, ReportItem
from app.rules.material_config import policy_references


def build_risk_report(application_id, result, documents, signature):
    if result.get('application_id') != application_id:
        raise ValueError('风险结果与申请不匹配')
    docs = {(d['id'], d['version']): d for d in documents if d.get('application_id') == application_id}
    items = []
    seen = set()
    entries = [('risk', item) for item in result.get('risk_items', [])]
    risk_ids = {entry.get('item_id') for entry in result.get('risk_items', []) if entry.get('item_id')}
    entries += [('missing', item) for item in result.get('missing_info', [])
                if not item.get('item_id') or item['item_id'] not in risk_ids]
    for index, (kind, item) in enumerate(entries, 1):
        item_id = str(item.get('item_id') or f'missing-{index}')
        if item_id in seen:
            item_id = f'{item_id}-{index}'
        seen.add(item_id)
        evidence, invalid = [], False
        for ref in item.get('evidence', []):
            if not isinstance(ref, dict):
                invalid = True
                continue
            doc = docs.get((ref.get('material_id'), ref.get('version_no')))
            location, quote = ref.get('location'), ref.get('quote')
            if not doc or not isinstance(location, str) or not isinstance(quote, str) or not quote or not any(
                section.get('location') == location and quote in section.get('text', '')
                for section in doc.get('parsed', {}).get('sections', [])
            ):
                invalid = True
                continue
            evidence.append(EvidenceRef(material_id=doc['id'], file_name=doc['filename'],
                version_no=doc['version'], location=location, quote=quote))
        ref = item.get('policy_ref')
        knowledge = KnowledgeItem(knowledge_id=ref[0], version=ref[1], requirement=ref[2]) if ref and tuple(ref) in policy_references() else None
        description = item.get('description') or item.get('message') or '需要人工核对。'
        if invalid:
            description += ' 部分证据未能按材料版本与位置核验，请人工核查。'
        items.append(ReportItem(item_id=item_id, item_type=kind, field_name=item.get('title') or item.get('category') or '待补充信息',
            match_status='insufficient_evidence' if invalid or kind == 'missing' else 'needs_review',
            application_value=None, material_value=None, evidence=evidence, knowledge_ref=knowledge,
            reason=description, confidence='未评定', suggested_human_action=item.get('suggested_human_action') or item.get('action') or '请人工核对。'))
    status = result.get('run_status', 'unknown')
    incomplete = status in ('degraded', 'dependency_degraded', 'input_invalid', 'failed', 'unknown')
    aspect = lambda text, state='needs_review': ReportAspect(status=state, summary=text)
    return Report(report_id='RPT-' + uuid4().hex, application_id=application_id,
        generated_at=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
        analysis_status='failed' if incomplete else 'needs_human_review', knowledge_version=str(result.get('rule_version', '未知')),
        error_message='风险 Workflow 未完整执行，请检查后重跑。' if incomplete else None,
        items=items, material_completeness=aspect('材料检查结果及缺失项见关注项，资料真实充分性需人工核验。', 'insufficient_evidence'),
        risk_prompts=[aspect('Workflow 已形成待人工复核的风险线索；无列出线索不代表无风险。')],
        policy_match=aspect('政策检索状态：' + str(result.get('retrieval_status', '未知')) + '；具体依据需人工核验。', 'not_evaluated'),
        precheck_advice=aspect('请逐项核对证据、缺口并记录人工复核意见；不构成授信决定。'),
        workflow_result=result, material_signature=[list(value) for value in signature])
