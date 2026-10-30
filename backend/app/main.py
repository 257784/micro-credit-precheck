"""FastAPI应用装配与旧入口兼容。"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.session import verify_database, get_engine
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.api import applications, documents, prechecks, reviews as review_routes, conversations, credit_assistant
from app.api.dependencies import repository, reviews
from app.api.applications import health, list_enterprises, list_applications, get_application
from app.api.documents import upload_document, list_documents, download_document
from app.api.prechecks import ask_policy, check_materials, risk_precheck
from app.api.reviews import require_risk_reviewer, start_review, submit_review

@asynccontextmanager
async def lifespan(app):
    verify_database()
    yield
    get_engine().dispose()


app = FastAPI(title="小微企业授信智能预审系统 F2", lifespan=lifespan)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': '数据库暂不可用，请稍后重试。'})

for routes in (conversations, documents, applications, prechecks, review_routes, credit_assistant):
    app.include_router(routes.router)
