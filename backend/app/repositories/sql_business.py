"""MySQL业务查询及复核事务；所有读取来自同一数据库。"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApplicationRow, EnterpriseRow, MaterialRow, ReportRow, StatusRow, ReviewRow, MaterialCheckRow, ApprovalRow
from app.db.session import get_engine
from app.repositories.reviews import ReviewConflict, STATUS_BY_ACTION
from app.schemas.business import Application, ApplicationDetail, ApplicationSummary, Enterprise, Material, Report, StatusEvent
from app.rules.application_states import ACTIVE_STATES, EDITABLE_STATES, RISK_REPORT_STATES, InvalidTransition, next_status
from app.observability.operation_audit import record as audit_operation


def checked_transition(current, action):
    try:
        return next_status(current, action)
    except InvalidTransition as error:
        raise ReviewConflict(str(error)) from None


class ApplicationRepository:
    def update_conditions(self, application_id, owner_id, values):
        from app.db.auth_models import ApplicationOwnerRow
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            owner = session.get(ApplicationOwnerRow, application_id)
            if row is None or owner is None or owner.user_id != owner_id:
                return 'not_found'
            if row.status not in EDITABLE_STATES:
                return 'conflict'
            key = 'is_used_equipment' if row.payload['product_type'].startswith('设备') else 'uses_order_contract'
            value = values.get(key)
            if value is not None:
                facts = dict(row.payload.get('condition_facts', {}))
                facts[key] = {'value': value, 'source': 'application_field', 'location': '企业材料声明',
                              'actor_id': owner_id, 'recorded_at': datetime.now(timezone.utc).isoformat()}
                row.payload = {**row.payload, 'condition_facts': facts}
            return 'updated'

    def assign_pending(self):
        from app.db.auth_models import UserRow
        with Session(get_engine()) as session, session.begin():
            managers = list(session.scalars(select(UserRow).where(UserRow.role == 'customer_manager',
                UserRow.active.is_(True)).order_by(UserRow.id).with_for_update()))
            if not managers:
                return
            rows = list(session.scalars(select(ApplicationRow).where(ApplicationRow.status.not_in(
                ('草稿', '审批通过', '审批未通过'))).order_by(ApplicationRow.submitted_at, ApplicationRow.id).with_for_update()))
            counts = {manager.id: 0 for manager in managers}
            for row in rows:
                manager_id = row.payload.get('account_manager_id')
                if manager_id in counts:
                    counts[manager_id] += 1
            for row in rows:
                if row.payload.get('assignment_pending') is not True:
                    continue
                manager = min(managers, key=lambda item: (counts[item.id], item.id))
                row.payload = {**row.payload, 'account_manager_id': manager.id,
                               'account_manager_name': manager.display_name, 'assignment_pending': False}
                counts[manager.id] += 1
                now = datetime.now(timezone.utc).isoformat(timespec='microseconds')
                event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=row.id,
                                    event_label='系统已自动分配客户经理', occurred_at=now)
                session.add(StatusRow(id=event.event_id, application_id=row.id, occurred_at=now,
                                      payload=event.model_dump()))

    def save_material_check(self, application_id, actor_id, signature, facts, result, checked_facts=None):
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if row is None or row.payload.get('condition_facts', {}) != facts:
                raise ReviewConflict('申请信息已变化，请重新检查。')
            current = sorted((m.id, m.category, m.version) for m in session.scalars(
                select(MaterialRow).where(MaterialRow.application_id == application_id)))
            if current != signature:
                raise ReviewConflict('材料已变化，请重新检查。')
            now = datetime.now(timezone.utc).isoformat(timespec='microseconds')
            item = {'check_id': 'CHK-' + uuid4().hex, 'checked_at': now, 'actor_id': actor_id,
                    'material_signature': signature, 'condition_facts': checked_facts if checked_facts is not None else facts, 'result': result}
            session.add(MaterialCheckRow(id=item['check_id'], application_id=application_id, checked_at=now, payload=item))
            return item

    def material_checks(self, application_id):
        with Session(get_engine()) as session:
            row = session.get(ApplicationRow, application_id)
            if row is None:
                return []
            signature = sorted((m.id, m.category, m.version) for m in session.scalars(
                select(MaterialRow).where(MaterialRow.application_id == application_id)))
            rows = session.scalars(select(MaterialCheckRow).where(MaterialCheckRow.application_id == application_id)
                                   .order_by(MaterialCheckRow.checked_at.desc(), MaterialCheckRow.id.desc()))
            return [{**item.payload, 'stale': sorted(tuple(v) for v in item.payload['material_signature']) != signature
                     or item.payload.get('condition_facts', {}) != row.payload.get('condition_facts', {})} for item in rows]

    def approval(self, application_id, actor, action, note=None):
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if row is None:
                raise ReviewConflict('申请状态已变化，不能执行审批操作。')
            status = checked_transition(row.status, {'start': 'approval_start', 'approve': 'approve', 'reject': 'reject'}.get(action))
            if action != 'start' and not (note or '').strip():
                raise ReviewConflict('请填写审批意见。')
            now = datetime.now(timezone.utc).isoformat(timespec='microseconds')
            record = {'action': action, 'actor_id': actor, 'note': note, 'occurred_at': now}
            audit_operation(session, actor_id=actor, actor_role='approver', object_id=application_id,
                action='approval_start' if action == 'start' else action,
                before={'status': row.status}, after={'status': status})
            session.add(ApprovalRow(id='APR-' + uuid4().hex, application_id=application_id, occurred_at=now, payload=record))
            row.status = status
            event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
                                event_label='审批状态：' + status, occurred_at=now)
            session.add(StatusRow(id=event.event_id, application_id=application_id, occurred_at=now,
                                  payload={**event.model_dump(), 'actor_id': actor}))
            return status

    def approval_records(self, application_id):
        with Session(get_engine()) as session:
            return [r.payload for r in session.scalars(select(ApprovalRow).where(
                ApprovalRow.application_id == application_id).order_by(ApprovalRow.occurred_at))]

    def suggest_supplement(self, application_id, actor, note):
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if row is None or row.status not in ACTIVE_STATES or row.payload.get('account_manager_id') != actor:
                raise ReviewConflict('当前申请不允许提出补件建议。')
            now = datetime.now(timezone.utc).isoformat(timespec='microseconds')
            event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
                                event_label='客户经理补件建议：' + note, occurred_at=now)
            session.add(StatusRow(id=event.event_id, application_id=application_id, occurred_at=now,
                                  payload={**event.model_dump(), 'actor_id': actor}))
            return row.status

    def save_workflow_report(self, report, signature, expected_status, actor_id):
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == report.application_id).with_for_update())
            if row is None or row.status != expected_status or row.status not in RISK_REPORT_STATES:
                raise ReviewConflict('申请状态已变化，请刷新后重新运行预审。')
            current = sorted((m.id, m.category, m.version) for m in session.scalars(
                select(MaterialRow).where(MaterialRow.application_id == report.application_id)))
            if current != signature:
                raise ReviewConflict('材料版本已变化，请重新运行预审。')
            session.add(ReportRow(id=report.report_id, application_id=report.application_id,
                generated_at=report.generated_at, payload=report.model_dump(mode='json')))
            audit_operation(session, actor_id=actor_id, actor_role='risk_reviewer', object_id=report.application_id,
                action='risk_report', before={'status': row.status},
                after={'status': row.status, 'report_id': report.report_id, 'analysis_status': report.analysis_status},
                result='degraded' if report.analysis_status == 'failed' else 'success')

    def list_for_admin(self):
        from app.db.auth_models import ApplicationOwnerRow
        with Session(get_engine()) as session:
            rows = list(session.scalars(select(ApplicationRow)))
            return [{'application_id': row.id, 'owner_id': (owner.user_id if owner else None),
                     'manager_id': row.payload.get('account_manager_id')}
                    for row in rows for owner in [session.get(ApplicationOwnerRow, row.id)]]

    def assign_history(self, application_id, actor_id, owner_id=None, manager_id=None):
        from app.db.auth_models import ApplicationOwnerRow, UserRow
        with Session(get_engine()) as session, session.begin():
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if row is None:
                return 'not_found'
            owner = session.get(ApplicationOwnerRow, application_id)
            existing_manager = row.payload.get('account_manager_id')
            if (owner_id and owner) or (manager_id and existing_manager and session.get(UserRow, existing_manager)):
                return 'conflict'
            for user_id, role in ((owner_id, 'enterprise'), (manager_id, 'customer_manager')):
                if user_id:
                    user = session.get(UserRow, user_id)
                    if not user or not user.active or user.role != role:
                        return 'invalid_user'
            if owner_id:
                session.add(ApplicationOwnerRow(application_id=application_id, user_id=owner_id))
            if manager_id:
                user = session.get(UserRow, manager_id)
                row.payload = {**row.payload, 'account_manager_id': manager_id, 'account_manager_name': user.display_name}
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
                event_label='管理员绑定申请归属', occurred_at=now)
            session.add(StatusRow(id=event.event_id, application_id=application_id, occurred_at=now,
                payload={**event.model_dump(), 'actor_id': actor_id, 'owner_id': owner_id, 'manager_id': manager_id}))
            return 'assigned'

    def material_signature(self, application_id):
        with Session(get_engine()) as session:
            return sorted((row.id, row.category, row.version) for row in session.scalars(
                select(MaterialRow).where(MaterialRow.application_id == application_id)))

    def resubmit(self, application_id, owner_id, signature, condition_facts=None, expected_facts=None, check_result=None):
        from app.db.auth_models import ApplicationOwnerRow, UserRow
        with Session(get_engine()) as session, session.begin():
            managers = list(session.scalars(select(UserRow).where(UserRow.role == 'customer_manager',
                UserRow.active.is_(True)).order_by(UserRow.id).with_for_update()))
            row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            owner = session.get(ApplicationOwnerRow, application_id)
            if row is None or owner is None or owner.user_id != owner_id:
                return 'not_found'
            try:
                target_status = next_status(row.status, 'submit')
            except InvalidTransition:
                return 'conflict'
            if not isinstance(check_result, dict) or check_result.get('application_id') != application_id or check_result.get('run_status') not in ('completed', 'completed_with_issues'):
                return 'check_required'
            if not all(isinstance(check_result.get(key), list) for key in ('missing_items', 'abnormal_items', 'pending_items')):
                return 'check_required'
            if check_result.get('missing_items') or check_result.get('abnormal_items') or any(
                item.get('kind') != 'sufficiency_review' for item in check_result.get('pending_items', [])):
                return 'check_required'
            current = sorted((material.id, material.category, material.version) for material in session.scalars(
                select(MaterialRow).where(MaterialRow.application_id == application_id)))
            if current != signature:
                return 'materials_changed'
            if expected_facts is not None and row.payload.get('condition_facts', {}) != expected_facts:
                return 'facts_changed'
            if condition_facts is not None:
                row.payload = {**row.payload, 'condition_facts': condition_facts}
            if check_result is not None:
                checked = datetime.now(timezone.utc).isoformat(timespec='microseconds')
                identifier = 'CHK-' + uuid4().hex
                session.add(MaterialCheckRow(id=identifier, application_id=application_id, checked_at=checked,
                    payload={'check_id': identifier, 'checked_at': checked, 'actor_id': owner_id,
                             'material_signature': signature, 'condition_facts': condition_facts or {}, 'result': check_result}))
            if row.payload.get('account_manager_id') in (None, '', 'UNASSIGNED') and managers:
                counts = {manager.id: 0 for manager in managers}
                for application in session.scalars(select(ApplicationRow).where(
                    ApplicationRow.status.not_in(('草稿', '审批通过', '审批未通过')))):
                    manager_id = application.payload.get('account_manager_id')
                    if manager_id in counts:
                        counts[manager_id] += 1
                manager = min(managers, key=lambda user: (counts[user.id], user.id))
                row.payload = {**row.payload, 'account_manager_id': manager.id, 'account_manager_name': manager.display_name}
            elif row.payload.get('account_manager_id') in (None, '', 'UNASSIGNED'):
                row.payload = {**row.payload, 'assignment_pending': True}
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            audit_operation(session, actor_id=owner_id, actor_role='enterprise', object_id=application_id,
                action='submit', before={'status': row.status}, after={'status': target_status})
            row.status = target_status
            event = StatusEvent(event_id='EVT-' + uuid4().hex, application_id=application_id,
                event_label='企业补充材料并重新提交，待风控复核', occurred_at=now)
            session.add(StatusRow(id=event.event_id, application_id=application_id,
                occurred_at=now, payload={**event.model_dump(), 'actor_id': owner_id}))
            return 'submitted'

    def list_unassigned(self):
        """仅返回认领所需的申请编号，不返回企业、材料或报告。"""
        with Session(get_engine()) as session:
            return [{'application_id': row.id} for row in session.scalars(select(ApplicationRow))
                    if row.payload.get('account_manager_id') in (None, '', 'UNASSIGNED')]

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

    def create_application(self, enterprise, application, event, owner_id=None):
        with Session(get_engine()) as session, session.begin():
            session.add(EnterpriseRow(id=enterprise.enterprise_id, payload=enterprise.model_dump()))
            session.flush()
            session.add(ApplicationRow(id=application.application_id, enterprise_id=enterprise.enterprise_id,
                status=application.status, submitted_at=application.submitted_at, payload=application.model_dump()))
            session.flush()
            session.add(StatusRow(id=event.event_id, application_id=application.application_id,
                occurred_at=event.occurred_at, payload=event.model_dump()))
            if owner_id is not None:
                from app.db.auth_models import ApplicationOwnerRow
                session.add(ApplicationOwnerRow(application_id=application.application_id, user_id=owner_id))
                audit_operation(session, actor_id=owner_id, actor_role='enterprise', object_id=application.application_id,
                    action='create_draft', after={'status': application.status})

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
               report_id=None, review_note=None, item_reviews=None, overall_adoption=None):
        # 行锁使状态检查、动作记录及状态更新成为一个原子操作。
        with Session(get_engine()) as session, session.begin():
            application = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application_id).with_for_update())
            if application is None or application.status != expected_status:
                raise ReviewConflict('申请状态已变化，请刷新后重试。')
            target_status = checked_transition(application.status, {'start': 'review_start', 'complete': 'review_complete',
                'request_supplement': 'request_supplement'}.get(kind))
            if kind != 'start' and not (review_note or '').strip():
                raise ReviewConflict('请填写复核意见或补件原因。')
            if kind == 'complete' and not report_id:
                raise ReviewConflict('无可用报告，不能完成复核。')
            if kind == 'complete' and overall_adoption not in ('accepted', 'partial', 'rejected'):
                raise ReviewConflict('请对 AI 报告选择采纳、部分采纳或不采纳。')
            if kind != 'start' and report_id is None and session.scalar(
                select(ReportRow.id).where(ReportRow.application_id == application_id).limit(1)
            ):
                raise ReviewConflict('预审报告已更新，请刷新后重新复核。')
            if report_id:
                report = session.get(ReportRow, report_id)
                if report is None or report.application_id != application_id:
                    raise ReviewConflict('报告与申请不匹配。')
                all_reports = list(session.scalars(select(ReportRow).where(ReportRow.application_id == application_id)))
                latest = max(all_reports, key=lambda item: datetime.fromisoformat(item.generated_at))
                if latest.id != report_id:
                    raise ReviewConflict('预审报告已更新，请刷新后重新复核。')
                if kind == 'complete':
                    if report.payload.get('analysis_status') == 'failed':
                        raise ReviewConflict('预审报告不可用，不能完成复核。')
                    expected_items = {item['item_id'] for item in report.payload.get('items', [])}
                    submitted_items = [item.item_id for item in (item_reviews or [])]
                    if set(submitted_items) != expected_items or len(submitted_items) != len(expected_items):
                        raise ReviewConflict('报告关注项已变化，请重新复核。')
                    if any(item.decision in ('corrected', 'partial', 'rejected') and not (item.correction_note or '').strip() for item in (item_reviews or [])):
                        raise ReviewConflict('修正、部分采纳或不采纳时请填写说明。')
                signature = report.payload.get('material_signature')
                if signature is not None and kind == 'complete':
                    current = sorted((m.id, m.category, m.version) for m in session.scalars(
                        select(MaterialRow).where(MaterialRow.application_id == application_id)))
                    if current != sorted(tuple(item) for item in signature):
                        raise ReviewConflict('报告所用材料已变化，请重新运行预审。')
            sequence = len(list(session.scalars(select(ReviewRow.id).where(ReviewRow.application_id == application_id)))) + 1
            identifier = 'ACT-' + uuid4().hex
            occurred = datetime.now(timezone.utc).isoformat(timespec='seconds')
            payload = dict(action_id=identifier, application_id=application_id, kind=kind,
                reviewer_id=reviewer_id, occurred_at=occurred, report_id=report_id,
                review_note=review_note, overall_adoption=overall_adoption,
                item_reviews_json=json.dumps([item.model_dump() for item in (item_reviews or [])], ensure_ascii=False))
            session.add(ReviewRow(id=identifier, application_id=application_id, report_id=report_id,
                sequence=sequence, occurred_at=occurred, payload=payload))
            audit_operation(session, actor_id=reviewer_id, actor_role='risk_reviewer', object_id=application_id,
                action={'start': 'review_start', 'complete': 'review_complete', 'request_supplement': 'request_supplement'}[kind],
                before={'status': application.status}, after={'status': target_status})
            application.status = target_status
