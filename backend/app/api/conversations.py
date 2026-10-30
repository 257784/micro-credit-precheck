"""对话生命周期与 SSE；有界队列和心跳不阻塞模型流的取消。"""

import asyncio
from contextlib import aclosing
import json

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from app.agents.policy_assistant import ConversationAgent
from app.agents.memory import ConversationStore, MessageRequest, SessionError

router = APIRouter(prefix="/api/policy/conversations")
store = ConversationStore()
agent = ConversationAgent(store)


@router.post("")
def create_conversation() -> dict:
    try:
        return store.create()
    except SessionError as error:
        raise HTTPException(error.status, str(error)) from None


@router.get("/{cid}")
def get_conversation(cid: str) -> dict:
    try:
        result = store.get(cid)
        result.pop("updated", None)
        return result
    except SessionError as error:
        raise HTTPException(error.status, str(error)) from None


@router.delete("/{cid}", status_code=204)
def delete_conversation(cid: str) -> Response:
    store.delete(cid)
    return Response(status_code=204)


@router.post("/{cid}/messages/stream")
async def stream_message(cid: str, message: MessageRequest, request: Request):
    try:
        session, turn, replay = store.begin(cid, message)
    except SessionError as error:
        raise HTTPException(error.status, str(error)) from None

    async def frames():
        queue = asyncio.Queue(maxsize=8)

        async def produce():
            try:
                async with aclosing(agent.events(cid, message, session, turn, replay)) as events:
                    async for event in events:
                        await queue.put(event)
                await queue.put(None)
            except asyncio.CancelledError:
                raise
            except Exception:
                store.fail(cid, message.request_id, "流式服务中断，请重试。")
                await queue.put(("error", {"code": "stream_failed", "message": "流式服务中断，请重试。", "rollback": True}))
                await queue.put(None)

        task = asyncio.create_task(produce())
        seq = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=5)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if item is None:
                    break
                event, payload = item
                seq += 1
                data = {**payload, "conversation_id": cid, "request_id": message.request_id,
                        "message_id": turn["message_id"], "seq": seq}
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            store.fail(cid, message.request_id, "连接已停止，本轮未完成。", stopped=True)

    return StreamingResponse(frames(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store", "X-Accel-Buffering": "no",
    })
