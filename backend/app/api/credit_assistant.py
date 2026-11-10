"""客户经理助手教学入口，固定服务端演示主体，单进程临时会话。"""
import asyncio
import json
import re
from threading import RLock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agents.context import RequestContext
from app.core.authorization import allowed_application_ids, can_access_application
from app.core.authentication import current_principal
from app.agents.credit_assistant import run_turn
from app.agents.assistant_result import build_result
from app.agents.condition_dialogue import QUESTIONS, explicit_conditions, interpret_condition, pending_from_results
from app.api.dependencies import reviews
from app.llm.deepseek import GenerationError
from app.llm.tool_client import ToolClient
from app.tools.assistant_tools import ToolExecutor

router = APIRouter(prefix='/api/credit-assistant')
sessions = {}
lock = RLock()


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    retry_of: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{8,80}$')
    application_id: str | None = Field(default=None, pattern=r'^APP-[A-Za-z0-9_-]{1,90}$')
    is_used_equipment: bool | None = Field(default=None, strict=True)
    clear_conditions: bool = Field(default=False, strict=True)


def require_session(cid, actor):
    session = sessions.get(cid)
    if not session or session['actor'] != actor or monotonic() - session['updated'] > 1800:
        raise HTTPException(404, '会话不存在或已过期。')
    session['updated'] = monotonic()
    return session


@router.post('/conversations')
def create_session(request: Request):
    with lock:
        now = monotonic()
        for key in list(sessions):
            if now - sessions[key]['updated'] > 1800:
                del sessions[key]
        if len(sessions) >= 50:
            raise HTTPException(429, '会话数量已达上限。')
        cid = uuid4().hex
        actor = request.state.principal.user_id
        sessions[cid] = {'actor': actor, 'updated': now, 'history': [], 'application_id': None,
                         'conditions': {}, 'pending_condition': None, 'pending_tool': None, 'requests': {}, 'running': False}
    return {'conversation_id': cid, 'notice': '助手只可访问当前账号负责的申请。'}


@router.get('/conversations/{cid}')
def get_session(cid: str, request: Request):
    with lock:
        session = require_session(cid, request.state.principal.user_id)
        if session['application_id'] and not can_access_application(request.state.principal, session['application_id']):
            raise HTTPException(404, '会话不可访问。')
        return {'conversation_id': cid, 'application_id': session['application_id'], 'history': list(session['history'])}


@router.get('/audit')
def get_audit(request: Request, actor: str | None = None, application_id: str | None = None,
              run_id: str | None = None, since: str | None = None):
    if request.state.principal.role != 'admin':
        raise HTTPException(403, '无权查看审计记录。')
    from datetime import datetime
    from app.observability.assistant_audit import AuditStore
    try:
        start = datetime.fromisoformat(since) if since else None
    except ValueError:
        raise HTTPException(422, '时间格式无效。') from None
    context = RequestContext(request.state.principal.user_id, 'admin', frozenset(), 'audit', 'audit', 'audit')
    return AuditStore().query(context, actor=actor, application_id=application_id, run_id=run_id, start=start)


@router.post('/conversations/{cid}/messages/stream')
async def stream(cid: str, request: Request, turn: TurnRequest):
    question = turn.question.strip()
    if not question:
        raise HTTPException(422, '问题不能为空。')
    with lock:
        principal = request.state.principal
        session = require_session(cid, principal.user_id)
        match = re.search(r'\bAPP-[A-Za-z0-9_-]{1,90}\b', question, flags=re.IGNORECASE)
        requested_id = turn.application_id or (match.group() if match else session['application_id'])
        if requested_id and not can_access_application(principal, requested_id):
            raise HTTPException(404, '申请不可访问。')
        previous = session['requests'].get(turn.request_id)
        signature = (question, turn.application_id, turn.is_used_equipment, turn.clear_conditions, turn.retry_of)
        if previous and previous['signature'] != signature:
            raise HTTPException(422, '请求编号已用于其他问题。')
        if previous and previous['status'] != 'complete':
            raise HTTPException(409, '请求正在处理或已停止，请使用新请求编号。')
        if session['running'] and not previous:
            raise HTTPException(409, '本会话已有正在处理的请求。')
        if turn.retry_of and not previous:
            original = session['requests'].get(turn.retry_of)
            if not original or original['status'] != 'failed':
                raise HTTPException(422, '重试来源不存在或尚未失败。')
        if previous:
            replay = previous['answer']
            replay_result = previous['result']
        else:
            replay = None
            replay_result = None
            session['running'] = True
            session['requests'][turn.request_id] = {'signature': signature, 'status': 'running', 'retry_of': turn.retry_of}
        application_id = requested_id
        conditions = dict(session['conditions']) if application_id == session['application_id'] else {}
        pending_condition = session.get('pending_condition') if application_id == session['application_id'] else None
        pending_tool = session.get('pending_tool') if pending_condition else None
        if turn.clear_conditions:
            conditions = {}
        if turn.is_used_equipment is not None:
            conditions['is_used_equipment'] = {'value': turn.is_used_equipment, 'source': 'manual_demo',
                'location': '用户本轮明确提交的教学条件，request_id=' + turn.request_id}
        condition_answer = interpret_condition(question, pending_condition)
        if condition_answer is not None:
            conditions[pending_condition] = {'value': condition_answer, 'source': 'manual_demo',
                'location': '客户经理本轮对话声明，request_id=' + turn.request_id}
        for field, value in explicit_conditions(question).items():
            conditions[field] = {'value': value, 'source': 'manual_demo',
                'location': '客户经理本轮对话声明，request_id=' + turn.request_id}
        history = list(session['history']) if application_id == session['application_id'] else []
    context = RequestContext(principal.user_id, principal.role, allowed_application_ids(principal), cid, turn.request_id, uuid4().hex)
    def still_authorized(target):
        current = current_principal(request.cookies.get('credit_session'))
        return bool(current and current.user_id == principal.user_id and current.role == principal.role
                    and can_access_application(current, target))
    if application_id:
        from dataclasses import replace
        context = replace(context, allowed_applications=context.allowed_applications & frozenset([application_id]))
    if replay_result is not None:
        from dataclasses import replace
        context = replace(context, run_id=replay_result['run_id'])

    async def frames():
        queue = asyncio.Queue(maxsize=8)
        next_pending = None
        next_tool = None
        async def emit(event, value):
            await queue.put((event, {**value, 'run_id': context.run_id}))
        async def produce():
            nonlocal next_pending, next_tool
            try:
                if replay is not None:
                    answer = replay
                    result = replay_result
                elif not application_id:
                    structured = build_result(context.run_id, None, [])
                    result = structured.model_dump()
                    answer = structured.summary
                elif pending_condition and condition_answer is None and question.strip().rstrip('。！!') in ('不确定', '不知道', '不清楚', '还不清楚', '未知'):
                    next_pending, next_tool = pending_condition, pending_tool
                    message = '请先核实相关事实；确认后可以直接在本对话回复。' + QUESTIONS[pending_condition]
                    structured = build_result(context.run_id, application_id, [])
                    structured = structured.model_copy(update={'status': 'needs_clarification', 'summary': message,
                        'missing_info': [message]})
                    result = structured.model_dump()
                    answer = structured.summary
                else:
                    await emit('progress', {'message': '正在选择只读工具并核对申请。'})
                    checker = lambda _context, target: still_authorized(target)
                    executor = ToolExecutor(reviews, authorization_check=checker)
                    if condition_answer is not None and pending_tool in ('check_materials', 'run_risk_precheck'):
                        call_id = uuid4().hex
                        await emit('tool_start', {'tool': pending_tool, 'tool_call_id': call_id})
                        started = monotonic()
                        outcome = await asyncio.to_thread(executor.execute, context, pending_tool,
                            json.dumps({'application_id': application_id}), call_id, conditions)
                        await emit('tool_end', {'tool': pending_tool, 'tool_call_id': call_id,
                            'status': outcome['status'], 'duration_ms': round((monotonic() - started) * 1000)})
                        tool_results = [(pending_tool, outcome)]
                    else:
                        _, tool_results = await run_turn(question, context, executor, ToolClient(), history, emit, conditions)
                    documents = []
                    if any(name in ('check_materials', 'run_risk_precheck') and item.get('status') == 'ok' for name, item in tool_results):
                        from app.services.documents import DocumentService
                        if not still_authorized(application_id):
                            raise GenerationError('unauthorized', '申请不可访问。')
                        documents = await asyncio.to_thread(DocumentService().list, application_id)
                    structured = build_result(context.run_id, application_id, tool_results, documents)
                    pending, next_tool = pending_from_results(tool_results)
                    next_pending = pending
                    if pending and structured.status not in ('failed', 'dependency_unavailable'):
                        conflicts = any(pending in result.get('workflow', {}).get('condition_conflicts', []) for _, result in tool_results)
                        prompt = ('申请声明与材料或本轮回答存在冲突，请风控要求补件，由企业核实并更新申请。' if conflicts else QUESTIONS[pending])
                        structured = structured.model_copy(update={'status': 'needs_clarification', 'summary': prompt,
                            'missing_info': list(dict.fromkeys(structured.missing_info + [prompt]))})
                    result = structured.model_dump()
                    answer = structured.summary
                if application_id and not still_authorized(application_id):
                    raise GenerationError('unauthorized', '申请不可访问。')
                await emit('result', {'result': result})
                await emit('answer', {'text': answer})
                await emit('done', {'status': 'partial' if result['status'] in ('failed', 'dependency_unavailable') else 'complete'})
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                await emit('error', {'message': '本轮处理超时，请稍后重试。'})
            except Exception as error:
                message = error.args[0] if isinstance(error, GenerationError) and error.args else '助手执行失败，请稍后重试。'
                await emit('error', {'message': message})
            finally:
                if asyncio.current_task().cancelling():
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        pass
                else:
                    await queue.put(None)
        task = asyncio.create_task(produce())
        final_answer = None
        final_result = None
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), 5)
                except TimeoutError:
                    yield ': heartbeat\n\n'
                    continue
                if item is None:
                    break
                event, data = item
                if event == 'answer':
                    final_answer = data['text']
                if event == 'result':
                    final_result = data['result']
                if event == 'done' and replay is None:
                    with lock:
                        current = require_session(cid, principal.user_id)
                        current['application_id'] = application_id
                        current['conditions'] = conditions
                        current['pending_condition'] = next_pending
                        current['pending_tool'] = next_tool
                        current['history'] = (history + [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': final_answer}])[-8:]
                        current['requests'][turn.request_id].update(status='complete', answer=final_answer, result=final_result)
                yield f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if replay is None:
                with lock:
                    current = sessions.get(cid)
                    if current:
                        current['running'] = False
                        if current['requests'][turn.request_id]['status'] == 'running':
                            current['requests'][turn.request_id]['status'] = 'failed'
    return StreamingResponse(frames(), media_type='text/event-stream', headers={'Cache-Control': 'no-store'})
