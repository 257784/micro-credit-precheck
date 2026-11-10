"""申请数据授权：不信任请求中的角色、申请归属或 Agent 工具参数。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.auth_models import ApplicationOwnerRow
from app.db.models import ApplicationRow, ReviewRow
from app.db.session import get_engine

RISK_VISIBLE_STATUSES = frozenset({'待风控复核', '风控复核中', '待审批', '审批中', '审批通过', '审批未通过'})
APPROVER_VISIBLE_STATUSES = frozenset({'待审批', '审批中', '审批通过', '审批未通过'})


def can_access_application(principal, application_id):
    with Session(get_engine()) as session:
        application = session.get(ApplicationRow, application_id)
        if application is None:
            return False
        if principal.role == 'risk_reviewer':
            return application.status in RISK_VISIBLE_STATUSES or (
                application.status == '待企业补充材料' and session.scalar(
                    select(ReviewRow.id).where(ReviewRow.application_id == application_id).limit(1)) is not None)
        if principal.role == 'enterprise':
            owner = session.get(ApplicationOwnerRow, application_id)
            return owner is not None and owner.user_id == principal.user_id
        if principal.role == 'approver':
            return application.status in APPROVER_VISIBLE_STATUSES
        if principal.role == 'customer_manager':
            return application.payload.get('account_manager_id') == principal.user_id
        return False


def allowed_application_ids(principal):
    with Session(get_engine()) as session:
        if principal.role == 'risk_reviewer':
            visible = set(session.scalars(select(ApplicationRow.id).where(ApplicationRow.status.in_(RISK_VISIBLE_STATUSES))))
            visible.update(session.scalars(select(ApplicationRow.id).where(
                ApplicationRow.status == '待企业补充材料',
                select(ReviewRow.id).where(ReviewRow.application_id == ApplicationRow.id).exists())))
            return frozenset(visible)
        if principal.role == 'enterprise':
            return frozenset(session.scalars(select(ApplicationOwnerRow.application_id).where(
                ApplicationOwnerRow.user_id == principal.user_id)))
        if principal.role == 'approver':
            return frozenset(session.scalars(select(ApplicationRow.id).where(ApplicationRow.status.in_(APPROVER_VISIBLE_STATUSES))))
        if principal.role == 'customer_manager':
            rows = session.scalars(select(ApplicationRow))
            return frozenset(row.id for row in rows if row.payload.get('account_manager_id') == principal.user_id)
        return frozenset()
