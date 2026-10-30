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

router = APIRouter()


@router.post('/api/applications', response_model=Application, status_code=201)
def create_application(submission: ApplicationSubmission, x_demo_role: str = Header(default='')):
    if x_demo_role != 'enterprise':
        raise HTTPException(403, '仅企业客户演示角色可以提交申请')
    return submit_application(dependencies.repository, submission)

@router.get("/api/health")
def health() -> dict[str, str]:
    """供本地启动检查使用。"""

    return {"status": "ok", "environment": os.getenv("APP_ENV", "development")}


@router.get("/api/enterprises", response_model=list[Enterprise])
def list_enterprises() -> list[Enterprise]:
    """列出虚构企业客户。"""

    return dependencies.repository.list_enterprises()


@router.get("/api/applications", response_model=list[ApplicationSummary])
def list_applications() -> list[ApplicationSummary]:
    """列出申请及其企业名称和最新报告状态。"""

    return dependencies.reviews.list_applications()


@router.get("/api/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str) -> ApplicationDetail:
    """返回单笔申请详情，不存在时返回 404。"""

    detail = dependencies.reviews.get_application(application_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    return detail
