import os
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from app.schemas.business import ApplicationDetail, ApplicationSummary, Enterprise, ReviewSubmission
from app.schemas.policy import QuestionRequest, QuestionResponse
from app.schemas.materials import CheckRequest
from app.services.reviews import ReviewConflict, ReviewInputError
from app.api import dependencies

router = APIRouter()

@router.post("/api/policy/ask", response_model=QuestionResponse)
def ask_policy(question: QuestionRequest) -> QuestionResponse:
    """教学政策解释；与复核写入服务分开，每次独立提问。"""
    from app.services.policy import PolicyQA

    return PolicyQA().answer(question)


@router.post("/api/applications/{application_id}/materials/check")
def check_materials(application_id: str, request: Request, submission: CheckRequest | None = None) -> dict:
    """只读教学Workflow；从服务器读取材料，不接收替换材料或状态操作。"""
    from app.workflows.materials import WorkflowInputError
    from app.services.prechecks import check_materials as execute

    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(404, "申请不存在")
    try:
        if request.state.principal.role != 'enterprise':
            raise HTTPException(403, '仅企业客户可以运行材料检查。')
        signature = dependencies.repository.material_signature(application_id)
        # 客户端不能用临时条件冒充企业已保存声明。
        result = execute(detail, CheckRequest())
        record = dependencies.repository.save_material_check(application_id, request.state.principal.user_id,
            signature, detail.application.condition_facts, result)
        return {**result, 'check_id': record['check_id'], 'checked_at': record['checked_at']}
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None
    except WorkflowInputError as error:
        raise HTTPException(422, str(error)) from None
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "完整性检查配置或教学输入无法读取，请检查后重试。") from None


@router.post("/api/applications/{application_id}/risk-precheck")
def risk_precheck(application_id: str, request: Request, submission: CheckRequest | None = None) -> dict:
    """风控运行后保存报告；客户经理仅运行只读预览。"""
    from app.services.prechecks import check_risks
    from app.workflows.materials import WorkflowInputError

    if request.state.principal.role != 'risk_reviewer':
        raise HTTPException(403, '仅风控专员可以运行风险预审。')
    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(404, "申请不存在")
    try:
        signature = dependencies.repository.material_signature(application_id)
        result = check_risks(detail, submission)
        if request.state.principal.role == 'risk_reviewer':
            from app.api.auth import require_principal
            from app.core.authorization import can_access_application
            from app.services.documents import DocumentService
            from app.services.risk_reports import build_risk_report
            principal = require_principal(request)
            if principal.user_id != request.state.principal.user_id or not can_access_application(principal, application_id):
                raise HTTPException(404, '申请不可访问。')
            report = build_risk_report(application_id, result, DocumentService().list(application_id), signature)
            dependencies.repository.save_workflow_report(report, signature, detail.application.status, principal.user_id)
            result['saved_report_id'] = report.report_id
        else:
            result['saved_report_id'] = None
        return result
    except ReviewConflict as error:
        raise HTTPException(409, str(error)) from None
    except WorkflowInputError as error:
        raise HTTPException(422, str(error)) from None
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "风险预审配置或教学输入无法读取。") from None
