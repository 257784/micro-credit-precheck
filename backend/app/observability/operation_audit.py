"""业务操作日志只接受枚举动作和有限字段，不接收正文或异常文本。"""
from datetime import datetime, timezone
from uuid import uuid4
import re

from sqlalchemy.orm import Session
from app.db.models import OperationAuditRow
from app.db.session import get_engine
from app.rules.application_states import ACTIVE_STATES, TERMINAL_STATES

ALLOWED_ACTIONS = frozenset({'create_draft', 'submit', 'review_start', 'review_complete',
    'request_supplement', 'review_submit', 'approval_start', 'approve', 'reject', 'risk_report'})
ALLOWED_RESULTS = frozenset({'success', 'failed', 'degraded'})
ALLOWED_VALUES = frozenset({'status', 'report_id', 'analysis_status'})


def record(session, *, actor_id, actor_role, object_id, action, before=None, after=None,
           result='success', reason_code=None):
    if action not in ALLOWED_ACTIONS or result not in ALLOWED_RESULTS:
        raise ValueError('invalid audit event')
    if reason_code not in (None, 'state_conflict', 'invalid_input', 'dependency_failure'):
        raise ValueError('invalid audit reason')
    for value in (before, after):
        if value is not None and (not isinstance(value, dict) or set(value) - ALLOWED_VALUES or
                                  any(not isinstance(v, str) or len(v) > 100 for v in value.values())):
            raise ValueError('invalid audit value')
        if value and ('status' in value and value['status'] not in ACTIVE_STATES | TERMINAL_STATES | {'草稿'} or
                      'analysis_status' in value and value['analysis_status'] not in {'failed', 'needs_human_review'} or
                      'report_id' in value and not re.fullmatch(r'RPT-[a-f0-9]{32}', value['report_id'])):
            raise ValueError('invalid audit value')
    session.add(OperationAuditRow(id=uuid4().hex, occurred_at=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
        actor_id=actor_id, actor_role=actor_role, object_type='application', object_id=object_id,
        action=action, before_value=before, after_value=after, result=result, reason_code=reason_code))


def record_failure(principal, application_id, action, reason_code):
    with Session(get_engine()) as session, session.begin():
        record(session, actor_id=principal.user_id, actor_role=principal.role, object_id=application_id,
               action=action, result='failed', reason_code=reason_code)
