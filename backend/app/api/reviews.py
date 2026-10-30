import os
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from app.schemas.business import ApplicationDetail, ApplicationSummary, Enterprise, ReviewSubmission
from app.schemas.policy import QuestionRequest, QuestionResponse
from app.schemas.materials import CheckRequest
from app.services.reviews import ReviewConflict, ReviewInputError
from app.api import dependencies

router = APIRouter()

def require_risk_reviewer(role: str) -> str:
    """教学角色边界；生产环境必须替换为真实身份认证。"""

    if role != "risk_reviewer":
        raise HTTPException(status_code=403, detail="只有风控专员可以提交复核操作")
    return "RISK-DEMO-001"


@router.post("/api/applications/{application_id}/review/start", response_model=ApplicationDetail)
def start_review(
    application_id: str, x_demo_role: str = Header(default="customer_manager")
) -> ApplicationDetail:
    """从待风控复核进入风控复核中。"""

    reviewer_id = require_risk_reviewer(x_demo_role)
    try:
        detail = dependencies.reviews.start(application_id, reviewer_id)
    except ReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if detail is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    return detail


@router.post("/api/applications/{application_id}/review/submit", response_model=ApplicationDetail)
def submit_review(
    application_id: str,
    submission: ReviewSubmission,
    x_demo_role: str = Header(default="customer_manager"),
) -> ApplicationDetail:
    """保存逐项处理和意见，并更新到待审批或待企业补充材料。"""

    reviewer_id = require_risk_reviewer(x_demo_role)
    try:
        detail = dependencies.reviews.submit(application_id, reviewer_id, submission)
    except ReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ReviewInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if detail is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    return detail
