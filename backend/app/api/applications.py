import os
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from app.schemas.business import ApplicationDetail, ApplicationSummary, Enterprise, ReviewSubmission
from app.schemas.policy import QuestionRequest, QuestionResponse
from app.schemas.materials import CheckRequest
from app.services.reviews import ReviewConflict, ReviewInputError
from app.api import dependencies
from app.schemas.business import Application, ApplicationSubmission
from app.services.submissions import submit_application
from app.core.authorization import allowed_application_ids
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone

router = APIRouter()


class ResubmitInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    is_used_equipment: bool | None = Field(default=None, strict=True)
    uses_order_contract: bool | None = Field(default=None, strict=True)


class AssignInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    owner_id: str | None = Field(default=None, min_length=1, max_length=64)
    manager_id: str | None = Field(default=None, min_length=1, max_length=64)


class ActionNote(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    note: str = Field(min_length=1, max_length=2000)


@router.post('/api/applications/{application_id}/conditions')
def update_conditions(application_id: str, body: ResubmitInput, request: Request):
    if request.state.principal.role != 'enterprise':
        raise HTTPException(403, '仅企业客户可以更新申请声明。')
    result = dependencies.repository.update_conditions(application_id, request.state.principal.user_id, body.model_dump())
    if result == 'not_found':
        raise HTTPException(404, '申请不可访问。')
    if result != 'updated':
        raise HTTPException(409, '当前状态不允许更新声明。')
    return {'status': result}


@router.get('/api/applications/{application_id}/material-checks')
def material_check_history(application_id: str):
    return dependencies.repository.material_checks(application_id)


@router.post('/api/applications/{application_id}/supplement-suggestion')
def supplement_suggestion(application_id: str, body: ActionNote, request: Request):
    if request.state.principal.role != 'customer_manager':
        raise HTTPException(403, '仅负责的客户经理可提出补件建议。')
    try:
        return {'status': dependencies.repository.suggest_supplement(application_id, request.state.principal.user_id, body.note)}
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None


@router.post('/api/applications/{application_id}/approval/start')
def start_approval(application_id: str, request: Request):
    if request.state.principal.role != 'approver':
        raise HTTPException(403, '仅审批人员可以审批。')
    try:
        return {'status': dependencies.repository.approval(application_id, request.state.principal.user_id, 'start')}
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None


@router.post('/api/applications/{application_id}/approval/{decision}')
def decide_approval(application_id: str, decision: str, body: ActionNote, request: Request):
    if request.state.principal.role != 'approver':
        raise HTTPException(403, '仅审批人员可以审批。')
    if decision not in ('approve', 'reject'):
        raise HTTPException(422, '无效审批决定。')
    try:
        return {'status': dependencies.repository.approval(application_id, request.state.principal.user_id, decision, body.note)}
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None


@router.get('/api/applications/{application_id}/approval-records')
def approval_records(application_id: str):
    return dependencies.repository.approval_records(application_id)


@router.post('/api/applications', response_model=Application, status_code=201)
def create_application(submission: ApplicationSubmission, request: Request):
    principal = request.state.principal
    if principal.role != 'enterprise':
        raise HTTPException(403, '仅企业客户可以提交申请')
    return submit_application(dependencies.repository, submission, owner_id=principal.user_id)


@router.get('/api/applications/unassigned')
def unassigned_applications(request: Request):
    if request.state.principal.role != 'customer_manager':
        raise HTTPException(403, '无权查看待认领申请')
    return dependencies.repository.list_unassigned()


@router.get('/api/applications/admin-index')
def admin_index(request: Request):
    if request.state.principal.role != 'admin':
        raise HTTPException(403, '无权查看归属目录')
    return dependencies.repository.list_for_admin()


@router.post('/api/applications/{application_id}/claim')
def claim_application(application_id: str, request: Request):
    principal = request.state.principal
    if principal.role != 'customer_manager':
        raise HTTPException(403, '无权认领申请')
    result = dependencies.repository.claim_application(application_id, principal.user_id, principal.display_name)
    if result == 'not_found':
        raise HTTPException(404, '申请不可访问')
    if result == 'already_assigned':
        raise HTTPException(409, '申请已被认领，请刷新')
    return {'status': 'claimed', 'application_id': application_id}


@router.post('/api/applications/{application_id}/assign')
def assign_application(application_id: str, body: AssignInput, request: Request):
    if request.state.principal.role != 'admin':
        raise HTTPException(403, '无权分配申请')
    if not body.owner_id and not body.manager_id:
        raise HTTPException(422, '请指定企业用户或客户经理')
    result = dependencies.repository.assign_history(application_id, request.state.principal.user_id, body.owner_id, body.manager_id)
    if result == 'not_found':
        raise HTTPException(404, '申请不存在')
    if result == 'conflict':
        raise HTTPException(409, '申请已有归属，不能覆盖')
    if result == 'invalid_user':
        raise HTTPException(422, '目标用户不存在、已停用或角色不匹配')
    return {'application_id': application_id, 'status': 'assigned'}


@router.post('/api/applications/{application_id}/resubmit')
def resubmit_application(application_id: str, body: ResubmitInput, request: Request):
    principal = request.state.principal
    if principal.role != 'enterprise':
        raise HTTPException(403, '仅企业客户可重新提交')
    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(404, '申请不可访问')
    if detail.application.status not in ('草稿', '待企业补充材料'):
        raise HTTPException(409, '当前状态不允许重新提交')
    signature = dependencies.repository.material_signature(application_id)
    from app.services.prechecks import check_materials
    expected_facts = dict(detail.application.condition_facts)
    conditions = dict(expected_facts)
    relevant = 'is_used_equipment' if detail.application.product_type.startswith('设备') else 'uses_order_contract'
    value = getattr(body, relevant)
    if value is not None:
        conditions[relevant] = {'value': value, 'source': 'application_field', 'location': '企业补件声明',
            'actor_id': principal.user_id, 'recorded_at': datetime.now(timezone.utc).isoformat()}
    detail.application = detail.application.model_copy(update={'condition_facts': conditions})
    result = check_materials(detail, CheckRequest())
    blocking = result['missing_items'] + result['abnormal_items'] + [
        item for item in result['pending_items'] if item.get('kind') != 'sufficiency_review']
    if result['run_status'] in ('input_invalid', 'dependency_degraded') or blocking:
        try:
            dependencies.repository.save_material_check(application_id, principal.user_id, signature, expected_facts, result, conditions)
        except ReviewConflict as error:
            raise HTTPException(409, str(error)) from None
        raise HTTPException(422, detail={'message': '初检发现缺失、异常或待确认项，请补充后重新提交。', 'issues': blocking})
    outcome = dependencies.repository.resubmit(application_id, principal.user_id, signature, conditions, expected_facts, result)
    if outcome == 'not_found':
        raise HTTPException(404, '申请不可访问')
    if outcome != 'submitted':
        raise HTTPException(409, '申请状态或材料已变化，请刷新后重试。')
    return {'application_id': application_id, 'status': '待风控复核',
            'notice': '材料已进入人工风控复核，提交不代表材料真实充分或授信通过。',
            'pending_human_review': result['pending_items']}

@router.get("/api/health")
def health() -> dict[str, str]:
    """供本地启动检查使用。"""

    return {"status": "ok", "environment": os.getenv("APP_ENV", "development")}


@router.get("/api/enterprises", response_model=list[Enterprise])
def list_enterprises() -> list[Enterprise]:
    """列出虚构企业客户。"""

    return dependencies.repository.list_enterprises()


@router.get("/api/applications", response_model=list[ApplicationSummary])
def list_applications(request: Request) -> list[ApplicationSummary]:
    """列出申请及其企业名称和最新报告状态。"""

    ids = allowed_application_ids(request.state.principal)
    items = [item for item in dependencies.reviews.list_applications() if item.application_id in ids]
    if request.state.principal.role == 'enterprise':
        return [item.model_copy(update={'report_status': None}) for item in items]
    return items


@router.get("/api/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str, request: Request) -> ApplicationDetail:
    """返回单笔申请详情，不存在时返回 404。"""

    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    if request.state.principal.role == 'enterprise':
        detail = detail.model_copy(update={'reports': [], 'reviews': []})
    return detail
