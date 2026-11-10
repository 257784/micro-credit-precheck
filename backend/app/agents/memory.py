"""单进程临时会话；成功轮次原子提交，失败回答不进入模型历史。"""

from copy import deepcopy
from threading import RLock
from time import monotonic
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")
    retry_of: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,80}$")

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class SessionError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class ConversationStore:
    """锁只保护内存操作，不跨网络或模型计算持有。"""

    def __init__(self, clock=monotonic) -> None:
        self.clock = clock
        self.sessions = {}
        self.lock = RLock()

    def _session(self, cid: str) -> dict:
        session = self.sessions.get(cid)
        if session is None or self.clock() - session["updated"] >= 1800:
            self.sessions.pop(cid, None)
            raise SessionError(404, "对话已过期或后端已重启，请开启新对话。")
        return session

    def create(self, owner_id: str | None = None) -> dict:
        with self.lock:
            self.sessions = {key: item for key, item in self.sessions.items()
                             if self.clock() - item["updated"] < 1800}
            if len(self.sessions) >= 50:
                raise SessionError(429, "临时对话数量已达上限，请结束已有对话或稍后再试。")
            cid = uuid4().hex
            self.sessions[cid] = {
                "conversation_id": cid, "owner_id": owner_id, "updated": self.clock(), "turns": [],
                "state": {"product": None, "facts": [], "pending_question": None,
                          "missing_slots": [], "clarification_count": 0},
            }
            return {"conversation_id": cid, "expires_in_seconds": 1800}

    def get(self, cid: str, owner_id: str | None = None) -> dict:
        with self.lock:
            session = self._session(cid)
            if session['owner_id'] != owner_id:
                raise SessionError(404, "对话不存在或已过期。")
            session["updated"] = self.clock()
            return deepcopy(session)

    def delete(self, cid: str, owner_id: str | None = None) -> None:
        with self.lock:
            session = self._session(cid)
            if session['owner_id'] != owner_id:
                raise SessionError(404, "对话不存在或已过期。")
            self.sessions.pop(cid, None)

    def begin(self, cid: str, request: MessageRequest, owner_id: str | None = None) -> tuple[dict, dict, bool]:
        with self.lock:
            session = self._session(cid)
            if session['owner_id'] != owner_id:
                raise SessionError(404, "对话不存在或已过期。")
            existing = next((t for t in session["turns"] if t["request_id"] == request.request_id), None)
            if existing:
                if existing["question"] != request.question:
                    raise SessionError(422, "同一请求编号不能用于不同问题。")
                if existing["status"] == "complete":
                    return deepcopy(session), deepcopy(existing), True
                raise SessionError(409, "请求正在处理或已中止；重试请使用新请求编号。")
            if any(t["status"] == "running" for t in session["turns"]):
                raise SessionError(409, "本对话仍有回答正在生成，请先停止或等待完成。")
            if len(session["turns"]) >= 40 or sum(t["status"] == "complete" for t in session["turns"]) >= 20:
                raise SessionError(409, "已达到本次对话长度限制，请开启新对话。")
            if request.retry_of:
                old = next((t for t in session["turns"] if t["request_id"] == request.retry_of), None)
                if not old or old["status"] not in ("failed", "stopped") or old["question"] != request.question:
                    raise SessionError(422, "只能重试本会话中未完成的同一个问题。")
            turn = {"request_id": request.request_id, "question": request.question,
                    "user_message_id": uuid4().hex, "message_id": uuid4().hex,
                    "retry_of": request.retry_of, "status": "running", "response": None,
                    "route": None, "error": None}
            session["turns"].append(turn)
            session["updated"] = self.clock()
            return deepcopy(session), deepcopy(turn), False

    def finish(self, cid: str, rid: str, response: dict, state: dict, route: dict) -> None:
        with self.lock:
            session = self._session(cid)
            turn = next(t for t in session["turns"] if t["request_id"] == rid)
            if turn["status"] != "running":
                raise SessionError(409, "本轮已停止，不能再次提交。")
            turn.update(status="complete", response=deepcopy(response), route=deepcopy(route))
            session["state"] = deepcopy(state)
            session["updated"] = self.clock()

    def fail(self, cid: str, rid: str, message: str, stopped: bool = False) -> None:
        with self.lock:
            session = self.sessions.get(cid)
            if not session:
                return
            turn = next((t for t in session["turns"] if t["request_id"] == rid), None)
            if turn and turn["status"] == "running":
                turn.update(status="stopped" if stopped else "failed", error=message)
                session["updated"] = self.clock()


def recent_history(session: dict) -> list[dict]:
    """按完整轮次截取，旧助手答案只能作为对话，不能作为政策证据。"""
    selected, size = [], 0
    complete = [turn for turn in session["turns"] if turn["status"] == "complete"]
    for turn in reversed(complete[-6:]):
        count = len(turn["question"]) + len(turn["response"]["answer"])
        if size + count > 12000:
            break
        selected.insert(0, {"user_message_id": turn["user_message_id"],
                            "question": turn["question"], "answer": turn["response"]["answer"]})
        size += count
    return selected
