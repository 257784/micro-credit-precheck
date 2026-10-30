"""MySQL业务查询及复核事务；所有读取来自同一数据库。"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationRow, EnterpriseRow, MaterialRow, ReportRow, StatusRow, ReviewRow
from app.db.session import get_engine
from app.repositories.reviews import ReviewConflict, STATUS_BY_ACTION
from app.schemas.business import Application, ApplicationDetail, ApplicationSummary, Enterprise, Material, Report, StatusEvent


class ApplicationRepository:
    def claim_application(self, application_id, manager_id, manager_name):
        """原子认领未分配申请；调用方必须先校验真实客户经理身份。"""
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if row is None:
                return 'not_found'
            payload = dict(row.payload)
            if payload.get('account_manager_id') not in (None, '', 'UNASSIGNED'):
                return 'already_assigned'
            payload.update(account_manager_id=manager_id, account_manager_name=manager_name)
            row.payload = payload
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
                event_label='客户经理已认领', occurred_at=now)
            session.add(StatusRow(id=event.event_id, application_id=application_id,
                occurred_at=now, payload={**event.model_dump(), 'actor_id': manager_id}))
            return 'claimed'

    def create_application(self, enterprise, application, event):
        with Session(get_engine()) as session, session.begin():
            session.add(EnterpriseRow(id=enterprise.enterprise_id, payload=enterprise.model_dump()))
            session.flush()
            session.add(ApplicationRow(id=application.application_id, enterprise_id=enterprise.enterprise_id,
                status=application.status, submitted_at=application.submitted_at, payload=application.model_dump()))
            session.flush()
            session.add(StatusRow(id=event.event_id, application_id=application.application_id,
                occurred_at=event.occurred_at, payload=event.model_dump()))

    def list_enterprises(self):
        with Session(get_engine()) as session:
            return [Enterprise.model_validate(row.payload) for row in session.scalars(select(EnterpriseRow).order_by(EnterpriseRow.id))]

    def list_applications(self):
        with Session(get_engine()) as session:
            result = []
            for row in session.scalars(select(ApplicationRow).order_by(ApplicationRow.id)):
                enterprise = session.get(EnterpriseRow, row.enterprise_id)
                reports = list(session.scalars(select(ReportRow).where(ReportRow.application_id == row.id)))
                latest = max(reports, key=lambda r: datetime.fromisoformat(r.generated_at), default=None)
                result.append(ApplicationSummary(**{**row.payload, 'status': row.status},
                    enterprise_name=enterprise.payload['enterprise_name'],
                    report_status=latest.payload['analysis_status'] if latest else None))
            return result

    def get_application(self, application_id):
        with Session(get_engine()) as session:
            row = session.get(ApplicationRow, application_id)
            if row is None:
                return None
            return ApplicationDetail(
                application=Application.model_validate({**row.payload, 'status': row.status}),
                enterprise=Enterprise.model_validate(session.get(EnterpriseRow, row.enterprise_id).payload),
                materials=[Material.model_validate(r.payload) for r in session.scalars(select(MaterialRow).where(
                    MaterialRow.application_id == application_id, MaterialRow.source == 'legacy').order_by(MaterialRow.id))],
                reports=[Report.model_validate(r.payload) for r in session.scalars(select(ReportRow).where(ReportRow.application_id == application_id))],
                status_history=[StatusEvent.model_validate(r.payload) for r in session.scalars(select(StatusRow).where(StatusRow.application_id == application_id))],
            )


class ReviewRepository:
    def actions_for(self, application_id):
        with Session(get_engine()) as session:
            return [row.payload for row in session.scalars(select(ReviewRow).where(
                ReviewRow.application_id == application_id).order_by(ReviewRow.sequence))]

    def append(self, application_id, base_status, expected_status, kind, reviewer_id,
               report_id=None, review_note=None, item_reviews=None):
        # 行锁使状态检查、动作记录及状态更新成为一个原子操作。
        with Session(get_engine()) as session, session.begin():
            application = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if application is None or application.status != expected_status:
                raise ReviewConflict('申请状态已变化，请刷新后重试。')
            if report_id:
                report = session.get(ReportRow, report_id)
                if report is None or report.application_id != application_id:
                    raise ReviewConflict('报告与申请不匹配。')
            sequence = len(list(session.scalars(select(ReviewRow.id).where(ReviewRow.application_id == application_id)))) + 1
            identifier = 'ACT-' + uuid4().hex
            occurred = datetime.now(timezone.utc).isoformat(timespec='seconds')
            payload = dict(action_id=identifier, application_id=application_id, kind=kind,
                reviewer_id=reviewer_id, occurred_at=occurred, report_id=report_id,
                review_note=review_note, item_reviews_json=json.dumps([item.model_dump() for item in (item_reviews or [])], ensure_ascii=False))
            session.add(ReviewRow(id=identifier, application_id=application_id, report_id=report_id,
                sequence=sequence, occurred_at=occurred, payload=payload))
            application.status = STATUS_BY_ACTION[kind]
