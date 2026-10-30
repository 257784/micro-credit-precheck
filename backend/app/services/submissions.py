"""企业教学申请提交。"""
from datetime import datetime, timezone
from uuid import uuid4
from app.schemas.business import Application, Enterprise, StatusEvent


def submit_application(repository, submission):
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    enterprise_id = 'ENT-' + uuid4().hex
    application_id = 'APP-' + uuid4().hex
    enterprise = Enterprise(enterprise_id=enterprise_id, enterprise_name=submission.enterprise_name,
        industry=submission.industry, registered_region=submission.registered_region, created_at=now)
    application = Application(application_id=application_id, enterprise_id=enterprise_id,
        product_type=submission.product_type, requested_amount=submission.requested_amount,
        purpose=submission.purpose, status='待企业补充材料', account_manager_id='UNASSIGNED',
        account_manager_name='待分配', submitted_at=now)
    event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
        event_label='申请已提交，待补充及核验材料', occurred_at=now)
    repository.create_application(enterprise, application, event)
    return application
