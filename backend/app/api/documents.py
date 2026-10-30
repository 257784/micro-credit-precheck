import os
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from app.schemas.business import ApplicationDetail, ApplicationSummary, Enterprise, ReviewSubmission
from app.schemas.policy import QuestionRequest, QuestionResponse
from app.schemas.materials import CheckRequest
from app.services.reviews import ReviewConflict, ReviewInputError
from app.api import dependencies
from app.services.documents import DocumentService

router = APIRouter()

@router.post("/api/applications/{application_id}/documents")
async def upload_document(application_id: str, category: str, filename: str, request: Request):
    from app.repositories.documents import DocumentStore, LIMIT
    from app.rules.material_config import load_configuration
    if dependencies.reviews.get_application(application_id) is None:
        raise HTTPException(404, "申请不存在")
    _, rules, _ = load_configuration()
    if category not in rules["types"]:
        raise HTTPException(422, "未知材料类别")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > LIMIT:
            raise HTTPException(413, "超过10MB工程限制")
    try:
        return DocumentService().upload(application_id, category, filename, bytes(content))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get("/api/applications/{application_id}/documents")
def list_documents(application_id: str):
    from app.repositories.documents import DocumentStore
    if dependencies.reviews.get_application(application_id) is None:
        raise HTTPException(404, "申请不存在")
    return DocumentService().list(application_id)


@router.get("/api/applications/{application_id}/documents/{document_id}")
def download_document(application_id: str, document_id: str):
    from app.repositories.documents import DocumentStore
    item = DocumentService().download(application_id, document_id)
    if item is None:
        raise HTTPException(404, "文件不存在")
    return FileResponse(item[0], filename=item[1])
