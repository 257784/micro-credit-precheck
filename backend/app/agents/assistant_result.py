"""从授权工具结果组装最终契约；材料引用和正文必须可在同申请中验证。"""
from app.schemas.assistant import AssistantResponse


def build_result(run_id, application_id, results, documents=None):
    facts, issues, risks, sources, missing, limitations = [], [], [], [], [], []
    notices = ['仅供虚构教学预审，须人工复核，不构成最终授信决定。']
    documents = documents or []
    verified = {(d['id'], d['version']): d for d in documents if d.get('application_id') == application_id}
    failed = False
    for name, result in results:
        if result.get('status') != 'ok':
            failed = True
            limitations.append(name + '：' + result.get('message', '工具未完成，请人工核对。'))
            continue
        if name != 'search_policy':
            target = result.get('application_id') or result.get('application', {}).get('application_id')
            if target != application_id:
                raise ValueError('工具结果申请编号不匹配')
        if name == 'get_application':
            a = result['application']
            for label, value in [('企业名称', result['enterprise_name']), ('产品', a['product_type']), ('申请状态', a['status'])]:
                facts.append({'label': label, 'value': str(value), 'source_tool': name})
        elif name == 'list_materials':
            facts.append({'label': '上传材料数量', 'value': str(len(result['materials'])), 'source_tool': name})
        elif name == 'search_policy':
            from app.rag.knowledge import load_chunks, load_config
            chunks, _ = load_chunks(load_config())
            known = {chunk.id: chunk for chunk in chunks}
            for source in result['sources']:
                chunk = known.get(source['chunk_id'])
                if not chunk or source['text'] != chunk.text or any(source[k] != chunk.metadata[k] for k in ('document_id', 'version', 'clause', 'source_path', 'source_line')):
                    missing.append('政策来源无法核验，已移除该来源。')
                    continue
                sources.append({key: source[key] for key in ('source_id', 'document_id', 'version', 'clause', 'source_path', 'source_line')})
        elif name in ('check_materials', 'run_risk_precheck'):
            workflow = result['workflow']
            if workflow.get('application_id') != application_id:
                raise ValueError('Workflow结果申请编号不匹配')
            limitations.extend(workflow.get('limitations', []))
            if workflow.get('run_status') in ('degraded', 'dependency_degraded', 'input_invalid'):
                failed = True
                limitations.append('Workflow未完整执行：' + str(workflow['run_status']))
            if name == 'check_materials':
                for category in ('missing_items', 'abnormal_items', 'pending_items'):
                    for item in workflow.get(category, []):
                        if item.get('material_id') and (item['material_id'], item.get('version_no')) not in verified:
                            missing.append('材料问题引用无法核验，已移除该项并请人工核对。')
                            continue
                        issues.append({'category': category, 'code': item.get('code'), 'description': item['message'],
                            'material_id': item.get('material_id'), 'version': item.get('version_no'),
                            'location': item.get('evidence_location'), 'action': item.get('action')})
            else:
                for item in workflow.get('risk_items', []):
                    evidence, valid = [], True
                    for ref in item.get('evidence', []):
                        if not isinstance(ref, dict):
                            valid = False
                            break
                        doc = verified.get((ref.get('material_id'), ref.get('version_no')))
                        quote, location = ref.get('quote'), ref.get('location')
                        sections = doc.get('parsed', {}).get('sections', []) if doc else []
                        if not isinstance(quote, str) or not quote or not isinstance(location, str) or not any(
                            s.get('location') == location and quote in s.get('text', '') for s in sections):
                            valid = False
                            break
                        evidence.append({'material_id': ref['material_id'], 'version': ref['version_no'],
                                         'location': location, 'quote': quote})
                    if item.get('origin') == 'model' and not evidence:
                        valid = False
                    if item.get('category') == 'amount_review' and len(evidence) < 2:
                        valid = False
                    if not valid:
                        missing.append('风险线索的材料证据无法核验，已移除该线索并请人工核对。')
                        continue
                    policy_ref = item.get('policy_ref')
                    if policy_ref:
                        from app.rules.material_config import policy_references
                        if tuple(policy_ref) not in policy_references():
                            missing.append('规则政策引用无法核验，已移除该引用。')
                            policy_ref = None
                    risks.append({'category': item['category'], 'description': item['description'],
                        'evidence': evidence, 'suggested_action': item.get('suggested_human_action'),
                        'policy_ref': policy_ref})
                missing.extend(item.get('message') or item.get('description') or '待人工核对。' for item in workflow.get('missing_info', []))
    if not application_id:
        status, summary = 'needs_clarification', '请先提供申请编号。'
    elif failed:
        status, summary = 'dependency_unavailable', '部分工具未完成，请查看限制并人工核对。'
    elif issues or risks or missing:
        status, summary = 'needs_review', '本次检查存在待人工核对的事项。'
    elif not results:
        status, summary = 'needs_clarification', '请补充需要查询的内容。'
    else:
        status, summary = 'completed', '已返回本轮工具结果；仍需人工核对。'
    return AssistantResponse.model_validate({'run_id': run_id, 'application_id': application_id, 'status': status,
        'summary': summary, 'facts': facts, 'material_issues': issues, 'risk_items': risks,
        'policy_sources': sources, 'missing_info': missing, 'need_human_review': True,
        'limitations': list(dict.fromkeys(limitations + notices))})
