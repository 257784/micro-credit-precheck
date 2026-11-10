"""管理员只读查询关键操作日志。"""
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import OperationAuditRow
from app.db.session import get_engine

router = APIRouter()


@router.get('/api/operation-audit')
def operation_audit(request: Request, application_id: str | None = Query(default=None, max_length=100),
                    limit: int = Query(default=50, ge=1, le=100)):
    if request.state.principal.role != 'admin':
        raise HTTPException(403, '仅管理员可以查看操作日志。')
    query = select(OperationAuditRow).order_by(OperationAuditRow.occurred_at.desc(), OperationAuditRow.id.desc()).limit(limit)
    if application_id:
        query = query.where(OperationAuditRow.object_type == 'application', OperationAuditRow.object_id == application_id)
    with Session(get_engine()) as session:
        return [{'id': row.id, 'occurred_at': row.occurred_at, 'actor_id': row.actor_id, 'actor_role': row.actor_role,
                 'object_type': row.object_type, 'object_id': row.object_id, 'action': row.action,
                 'before': row.before_value, 'after': row.after_value, 'result': row.result,
                 'reason_code': row.reason_code} for row in session.scalars(query)]
