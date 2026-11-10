"""只接受当前对话中明确的条件声明；不能从材料指令推断身份或权限。"""
import re

QUESTIONS = {
    'is_used_equipment': '请确认本次拟购设备是二手设备还是全新设备？',
    'uses_order_contract': '请确认本次用途是否以具体订单或合同作为依据？',
}


def interpret_condition(text, pending):
    if pending not in QUESTIONS:
        return None
    text = text.strip().rstrip('。！!，, ')
    if not text or re.search(r'不确定|不知道|尚未确认|可能|大概|或者|还是|吗|么|？|\?', text):
        return None
    if text in ('是', '是的', '对', '对的', '确认是'):
        return True
    if text in ('否', '不是', '不是的', '不', '没有', '确认不是'):
        return False
    if pending == 'is_used_equipment':
        yes = bool(re.search(r'^(?:是|购买|采购|拟购|买的是)?二手(?:设备|的)?$', text))
        no = bool(re.search(r'^(?:是|购买|采购|拟购|买的是)?(?:全新|新的|新设备|全新设备|不是二手设备|不是二手)$', text))
    else:
        yes = bool(re.search(r'^(?:是的，?)?以(?:具体)?(?:订单|合同|订单或合同)(?:作为|为)(?:资金)?用途依据$', text))
        no = bool(re.search(r'^(?:不以|没有以|未以).*(?:订单|合同).*(?:依据|用途)$', text))
    return yes if yes != no else None


def explicit_conditions(text):
    """仅识别明确陈述；含疑问、不确定或相反表述时不猜测。"""
    if re.search(r'不确定|不知道|尚未确认|可能|大概|或者|还是|是否|是不是|吗|么|？|\?', text):
        return {}
    patterns = {
        'is_used_equipment': (r'(?<!不)(?<!未)(?<!没有)(?<!购)(?:是|购买|购置|采购|拟购|买)(?:一台|一套)?二手设备',
                              r'(?<!不)(?<!未)(?<!没有)(?<!购)(?:是|购买|购置|采购|拟购|买)(?:一台|一套)?(?:全新设备|新设备)|不是二手设备'),
        'uses_order_contract': (r'(?<!不)(?<!未)(?<!没有)以(?:具体)?(?:订单|合同|订单或合同)作为用途依据',
                                r'(?:不|未|没有)以(?:具体)?(?:订单|合同|订单或合同)作为用途依据'),
    }
    values = {}
    for field, (yes_pattern, no_pattern) in patterns.items():
        negative = bool(re.search(no_pattern, text))
        positive = bool(re.search(yes_pattern, text))
        if positive != negative:
            values[field] = positive
    return values


def pending_from_results(results):
    for name, result in results:
        if name not in ('check_materials', 'run_risk_precheck') or result.get('status') != 'ok':
            continue
        flow = result.get('workflow', {})
        issues = flow.get('pending_items', []) + flow.get('risk_items', []) + flow.get('missing_info', [])
        for item in issues:
            if not isinstance(item, dict):
                continue
            text = ' '.join(str(item.get(k) or '') for k in ('action', 'suggested_human_action', 'description', 'message'))
            if '设备是否为二手' in text:
                return 'is_used_equipment', name
            if '是否以具体订单或合同为用途依据' in text:
                return 'uses_order_contract', name
    return None, None
