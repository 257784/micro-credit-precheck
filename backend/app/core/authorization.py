"""申请数据授权：不信任请求中的角色、申请归属或 Agent 工具参数。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.auth_models import ApplicationOwnerRow
from app.db.models import ApplicationRow
from app.db.session import get_engine


def can_access_application(principal, application_id):
    with Session(get_engine()) as session:
        application = session.get(ApplicationRow, application_id)
        if application is None:
            return False
        if principal.role == 'risk_reviewer':
            return True
        if principal.role == 'enterprise':
            owner = session.get(ApplicationOwnerRow, application_id)
            return owner is not None and owner.user_id == principal.user_id
        if principal.role == 'customer_manager':
            return application.payload.get('account_manager_id') == principal.user_id
        return False


def allowed_application_ids(principal):
    with Session(get_engine()) as session:
        if principal.role == 'risk_reviewer':
            return frozenset(session.scalars(select(ApplicationRow.id)))
        if principal.role == 'enterprise':
            return frozenset(session.scalars(select(ApplicationOwnerRow.application_id).where(
                ApplicationOwnerRow.user_id == principal.user_id)))
        if principal.role == 'customer_manager':
            rows = session.scalars(select(ApplicationRow))
            return frozenset(row.id for row in rows if row.payload.get('account_manager_id') == principal.user_id)
        return frozenset()
