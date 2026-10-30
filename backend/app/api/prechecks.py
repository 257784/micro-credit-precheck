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
def check_materials(application_id: str, submission: CheckRequest | None = None) -> dict:
    """只读教学Workflow；从服务器读取材料，不接收替换材料或状态操作。"""
    from app.workflows.materials import WorkflowInputError
    from app.services.prechecks import check_materials as execute

    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(404, "申请不存在")
    try:
        return execute(detail, submission)
    except WorkflowInputError as error:
        raise HTTPException(422, str(error)) from None
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "完整性检查配置或教学输入无法读取，请检查后重试。") from None


@router.post("/api/applications/{application_id}/risk-precheck")
def risk_precheck(application_id: str, submission: CheckRequest | None = None) -> dict:
    """只读执行风险预审，材料和申请均从服务端读取。"""
    from app.services.prechecks import check_risks
    from app.workflows.materials import WorkflowInputError

    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(404, "申请不存在")
    try:
        return check_risks(detail, submission)
    except WorkflowInputError as error:
        raise HTTPException(422, str(error)) from None
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "风险预审配置或教学输入无法读取。") from None
