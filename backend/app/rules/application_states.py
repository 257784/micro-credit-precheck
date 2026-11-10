"""教学申请状态及业务动作；身份授权和业务前置检查由调用方负责。"""

TRANSITIONS = {
    'submit': {'草稿': '待风控复核', '待企业补充材料': '待风控复核'},
    'review_start': {'待风控复核': '风控复核中'},
    'review_complete': {'风控复核中': '待审批'},
    'request_supplement': {'风控复核中': '待企业补充材料'},
    'approval_start': {'待审批': '审批中'},
    'approve': {'审批中': '审批通过'},
    'reject': {'审批中': '审批未通过'},
}

TERMINAL_STATES = frozenset({'审批通过', '审批未通过'})
EDITABLE_STATES = frozenset({'草稿', '待企业补充材料'})
RISK_REPORT_STATES = frozenset({'待风控复核', '风控复核中'})
ACTIVE_STATES = frozenset({'待企业补充材料', '待风控复核', '风控复核中', '待审批', '审批中'})


class InvalidTransition(ValueError):
    """动作不适用于当前状态，调用方应返回业务冲突。"""


def next_status(current, action):
    target = TRANSITIONS.get(action, {}).get(current)
    if target is None:
        raise InvalidTransition(f'当前状态“{current}”不允许执行该操作，请刷新后重试。')
    return target


def require_state(current, allowed):
    if current not in allowed:
        raise InvalidTransition(f'当前状态“{current}”不允许执行该操作，请刷新后重试。')
