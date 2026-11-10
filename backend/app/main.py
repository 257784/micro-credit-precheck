"""FastAPI应用装配与旧入口兼容。"""
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from app.db.session import verify_database, get_engine
from sqlalchemy.exc import SQLAlchemyError
from fastapi.responses import JSONResponse
from app.api import applications, documents, prechecks, reviews as review_routes, conversations, credit_assistant, auth, operation_audit
from app.core.authorization import can_access_application
import re
from urllib.parse import urlsplit
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


@app.middleware('http')
async def authenticated_api(request: Request, call_next):
    path = request.url.path
    if not path.startswith('/api/') or path == '/api/health':
        return await call_next(request)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and urlsplit(origin).netloc != request.headers.get('host'):
            return JSONResponse(status_code=403, content={'detail': '请求来源不允许。'})
    if path == '/api/auth/login':
        return await call_next(request)
    try:
        principal = auth.require_principal(request)
    except Exception as error:
        from fastapi import HTTPException
        if isinstance(error, HTTPException):
            return JSONResponse(status_code=error.status_code, content={'detail': error.detail})
        raise
    request.state.principal = principal
    if path.startswith('/api/policy/') and principal.role not in ('enterprise', 'customer_manager', 'risk_reviewer', 'approver'):
        return JSONResponse(status_code=403, content={'detail': '无权使用政策问答。'})
    if path == '/api/enterprises':
        return JSONResponse(status_code=403, content={'detail': '无权查看企业列表。'})
    if path.startswith('/api/credit-assistant') and not (
        principal.role == 'customer_manager' or (path == '/api/credit-assistant/audit' and principal.role == 'admin')
    ):
        return JSONResponse(status_code=403, content={'detail': '无权使用客户经理助手。'})
    match = re.match(r'^/api/applications/([^/]+)(?:/(.*))?$', path)
    if path in ('/api/applications/unassigned', '/api/applications/admin-index') or (match and match.group(2) in ('claim', 'assign')):
        return JSONResponse(status_code=403, content={'detail': '申请由系统自动分配。'})
    if match and match.group(1) not in ('unassigned', 'admin-index'):
        application_id, suffix = match.groups()
        if suffix == 'assign' and request.method == 'POST':
            if principal.role != 'admin':
                return JSONResponse(status_code=403, content={'detail': '无权分配申请。'})
        elif suffix == 'claim' and request.method == 'POST':
            if principal.role != 'customer_manager':
                return JSONResponse(status_code=403, content={'detail': '无权认领申请。'})
        elif not can_access_application(principal, application_id):
            return JSONResponse(status_code=404, content={'detail': '申请不可访问。'})
        elif principal.role == 'enterprise' and not (suffix is None or (suffix or '').startswith('documents') or suffix in ('resubmit', 'conditions', 'materials/check', 'material-checks')):
            return JSONResponse(status_code=403, content={'detail': '无权查看内部预审信息。'})
        elif suffix and suffix.startswith('review/') and principal.role != 'risk_reviewer':
            return JSONResponse(status_code=403, content={'detail': '无权提交风控复核。'})
        elif suffix and suffix.startswith('approval/') and principal.role != 'approver':
            return JSONResponse(status_code=403, content={'detail': '无权提交审批。'})
        elif suffix == 'documents' and request.method == 'POST' and principal.role != 'enterprise':
            return JSONResponse(status_code=403, content={'detail': '仅企业客户可上传材料。'})
    response = await call_next(request)
    if match and request.method == 'POST' and response.status_code in (409, 422, 500, 503):
        application_id, suffix = match.groups()
        action = {'resubmit': 'submit', 'review/start': 'review_start', 'review/submit': 'review_submit',
                  'approval/start': 'approval_start', 'approval/approve': 'approve',
                  'approval/reject': 'reject', 'risk-precheck': 'risk_report'}.get(suffix)
        if action:
            from app.observability.operation_audit import record_failure
            reason = 'state_conflict' if response.status_code == 409 else 'invalid_input' if response.status_code == 422 else 'dependency_failure'
            try:
                record_failure(principal, application_id, action, reason)
            except SQLAlchemyError:
                return JSONResponse(status_code=503, content={'detail': '操作日志暂不可用，请稍后重试。'})
    return response


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': '数据库暂不可用，请稍后重试。'})

for routes in (auth, conversations, documents, applications, prechecks, review_routes, credit_assistant, operation_audit):
    app.include_router(routes.router)
