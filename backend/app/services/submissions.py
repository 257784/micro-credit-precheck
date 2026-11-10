"""企业教学申请提交。"""
from datetime import datetime, timezone
from uuid import uuid4
from app.schemas.business import Application, Enterprise, StatusEvent


def submit_application(repository, submission, owner_id=None):
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    enterprise_id = 'ENT-' + uuid4().hex
    application_id = 'APP-' + uuid4().hex
    enterprise = Enterprise(enterprise_id=enterprise_id, enterprise_name=submission.enterprise_name,
        industry=submission.industry, registered_region=submission.registered_region, created_at=now)
    allowed = 'is_used_equipment' if submission.product_type.startswith('设备') else 'uses_order_contract'
    condition_facts = {allowed: {'value': getattr(submission, allowed), 'source': 'application_field',
        'location': '企业申请声明', 'actor_id': owner_id, 'recorded_at': now}} if getattr(submission, allowed) is not None else {}
    application = Application(application_id=application_id, enterprise_id=enterprise_id,
        product_type=submission.product_type, requested_amount=submission.requested_amount,
        purpose=submission.purpose, status='草稿', account_manager_id='UNASSIGNED',
        account_manager_name='待分配', submitted_at=now, condition_facts=condition_facts)
    event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
        event_label='企业已保存申请草稿', occurred_at=now)
    repository.create_application(enterprise, application, event, owner_id=owner_id)
    return application
