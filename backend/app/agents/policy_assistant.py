"""多轮只读政策 Agent：范围识别、当前索引检索、逐要点校验及原子提交。"""

import asyncio
from contextlib import aclosing
import json
import re
from time import perf_counter

from app.llm.streaming import AsyncDeepSeek
from app.agents.memory import SessionError, recent_history
from app.llm.deepseek import GenerationError, Settings
from app.rag.knowledge import PRODUCTS
from app.schemas.policy import QuestionResponse
from app.services.policy import PROMPT, make_sources, validate_draft
from app.agents.policy_scope import catalog_and_chunks, resolve_route
from app.llm.stream_json import StatementParser


def retrieve_for_route(route, products, chunks, config, signature) -> list:
    from app.rag.vector_store import query, query_filtered

    question = route.standalone_question
    if route.intent == "common_rule":
        where = {"$and": [{"status": "teaching_draft"}, {"mode": "offline_teaching"},
                           *[{f"applies_{p['id']}": True} for p in products]]}
        return query_filtered(config, signature, question, where)[:6]
    if route.resolved_product_id and route.intent == "policy_question":
        return query(config, signature, question, route.resolved_product_id, 8, "cpu")[:6]
    # 比较/产品介绍先保证各产品的范围依据，不让单一排名吞掉另一产品。
    selected, seen = [], set()
    refs = {p["id"]: p["scope_refs"] for p in products}
    by_ref = {(c.metadata["document_id"], c.metadata["clause"], c.metadata["version"]): c for c in chunks}
    ids = route.candidate_product_ids or list(refs)
    for pid in ids:
        for ref in refs[pid][:2]:
            chunk = by_ref[tuple(ref)]
            if chunk.id not in seen:
                selected.append({"id": chunk.id, "text": chunk.text, "metadata": chunk.metadata,
                                 "cosine_distance": None})
                seen.add(chunk.id)
    if route.intent == "comparison":
        for pid in ids:
            for item in query(config, signature, question, pid, 8, "cpu"):
                if item["id"] not in seen:
                    selected.append(item)
                    seen.add(item["id"])
                    break
    return selected[:6]


def next_state(session: dict, route, response: QuestionResponse, question: str) -> dict:
    old = session["state"]
    reset = route.reset_scope or (route.resolved_product_id and route.resolved_product_id != old["product"])
    facts = [] if reset else list(old["facts"])
    for fact in route.facts_with_message_ids:
        facts = [item for item in facts if item["field"] != fact.field]
        facts.append(fact.model_dump())
    clarifying = response.status == "needs_clarification"
    return {"product": route.resolved_product_id or (None if reset else old["product"]),
            "facts": facts, "missing_slots": response.missing_information,
            "pending_question": route.standalone_question if clarifying else None,
            "clarification_count": old["clarification_count"] + 1 if clarifying else 0}


def final_response(draft, sources, model: str) -> QuestionResponse:
    heading = {"answered": "", "needs_clarification": "还需补充信息。",
               "insufficient_evidence": "当前依据不足以完整回答。"}[draft.status]
    cited = list(dict.fromkeys(e.source_id for statement in draft.statements for e in statement.evidence))
    lines = [s.text + " " + " ".join(f"[{sid}]" for sid in dict.fromkeys(e.source_id for e in s.evidence))
             for s in draft.statements]
    return QuestionResponse(status=draft.status, answer="\n".join(([heading] if heading else []) + lines),
                            statements=draft.statements, missing_information=draft.missing_information,
                            sources=sources, cited_source_ids=cited, model=model,
                            prompt_version="policy-conversation-v1")


def validate_scope(draft, route) -> None:
    if route.resolved_product_id != "working_capital":
        return
    for text in [s.text for s in draft.statements] + draft.missing_information:
        for sentence in re.split(r"[。；\n]", text):
            if re.search(r"设备价格依据缺失|补充设备|提供设备采购|核实设备价格", sentence) and not re.search(
                r"无需|不要求|不得|不应|不适用", sentence
            ):
                raise GenerationError("scope_mismatch", "回答混入其他产品要求，已撤回，请重新提问。")


class ConversationAgent:
    def __init__(self, store, client_factory=None, retriever=None, catalog_loader=None) -> None:
        self.store = store
        self.client_factory = client_factory or (lambda: AsyncDeepSeek(Settings.from_environment()))
        self.retriever = retriever or retrieve_for_route
        self.catalog_loader = catalog_loader or catalog_and_chunks

    async def events(self, cid: str, request, session: dict, turn: dict, replay: bool = False):
        started = perf_counter()
        yield "meta", {"replayed": replay}
        if replay:
            yield "done", {"response": turn["response"], "route": turn["route"]}
            return
        try:
            async with asyncio.timeout(120):
                async with aclosing(self._run(cid, request, session, turn, started)) as running:
                    async for event in running:
                        yield event
        except asyncio.CancelledError:
            self.store.fail(cid, request.request_id, "已停止，本轮未完成。", stopped=True)
            raise
        except TimeoutError:
            self.store.fail(cid, request.request_id, "本轮超时。")
            yield "error", {"code": "timeout", "message": "本轮超时，已撤回未完成回答，请重试。", "rollback": True}
        except GenerationError as error:
            self.store.fail(cid, request.request_id, str(error))
            yield "error", {"code": error.code, "message": str(error), "rollback": True}
        except (OSError, ValueError, KeyError, ImportError, RuntimeError, SessionError, TypeError):
            message = "本轮未完成，请检查本地检索或模型服务后重试。"
            self.store.fail(cid, request.request_id, message)
            yield "error", {"code": "conversation_failed", "message": message, "rollback": True}
        finally:
            self.store.fail(cid, request.request_id, "连接中断，本轮未完成。", stopped=True)

    async def _run(self, cid, request, session, turn, started):
        yield "status", {"stage": "routing", "message": "正在理解你的需求…"}
        products, chunks, config, signature = self.catalog_loader()
        known_ids = {c.metadata["document_id"] for c in chunks}
        if set(re.findall(r"CC-[A-Z]+-\d{3}", request.question)) - known_ids:
            response = QuestionResponse(status="insufficient_evidence", answer="知识库未收录所请求文号，不能编造政策依据。",
                                        missing_information=["请确认文号或提供适用政策。"])
            self.store.finish(cid, request.request_id, response.model_dump(), session["state"], {})
            yield "done", {"response": response.model_dump(), "route": {}}
            return
        history = recent_history(session)
        # 明确产品/通用规则/职责边界可不调用路由模型，其他情况按需创建客户端。
        setup_error = None
        try:
            client = self.client_factory()
        except GenerationError as error:
            client = None
            setup_error = error
        try:
            route = await resolve_route(request.question, session, turn, history, products, client)
        except GenerationError:
            if setup_error is not None:
                raise setup_error
            raise
        scope = PRODUCTS.get(route.resolved_product_id)
        yield "scope", {"label": scope or ("共通规则" if route.intent == "common_rule" else "范围待明确"),
                        "basis": route.basis}
        if route.intent in ("clarification_needed", "out_of_scope"):
            is_clarify = route.intent == "clarification_needed"
            question = route.clarification_question or "本助手仅解释政策，不能批准申请或改变复核状态。"
            if is_clarify and session["state"]["clarification_count"] >= 2:
                question = "现有知识库只能解释经营周转和设备更新相关政策。你可以说明准备购买什么、资金如何使用；目前无法确定时可先了解两类用途的区别。"
            response = QuestionResponse(status="needs_clarification" if is_clarify else "out_of_scope",
                                        answer=question, missing_information=route.missing_slots,
                                        prompt_version="policy-conversation-v1")
            if is_clarify:
                yield "clarification", {"question": question, "missing_slots": route.missing_slots}
        else:
            yield "status", {"stage": "retrieval", "message": "正在检索本轮适用条款…"}
            rows = await asyncio.to_thread(self.retriever, route, products, chunks, config, signature)
            sources = make_sources(rows)
            yield "sources", {"sources": [s.model_dump() for s in sources]}
            if not sources:
                response = QuestionResponse(status="insufficient_evidence", answer="未找到适用条款，请补充问题或确认政策范围。")
            else:
                if client is None:
                    client = self.client_factory()
                if sum(len(s.text) for s in sources) > 24000:
                    raise GenerationError("context_too_long", "政策上下文过长，请缩小问题范围。")
                yield "status", {"stage": "generating", "message": "正在生成并核对引用…"}
                supplemental = """按当前路由范围解释。旧助手回答不是证据，不沿用旧引用编号。
共通段落可能举不同产品的例子，只解释与本次用途相关部分，不把设备价格缺口强加给经营周转用途。
比较时按产品分组；当前目录只有两种产品，不判定符合准入。保留条件与例外。
请依次输出status、statements、missing_information；每个要点都带完整引文。
"""
                payload = {"question": request.question, "resolved_question": route.standalone_question,
                           "route": route.model_dump(), "user_facts": next_state(
                               session, route, QuestionResponse(status="answered", answer=""), request.question,
                           )["facts"],
                           "history_as_dialogue_not_evidence": history,
                           "sources": [s.model_dump() for s in sources]}
                parser = StatementParser()
                messages = [{"role": "system", "content": PROMPT + supplemental},
                            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
                index = 0
                async with aclosing(client.stream(messages)) as upstream:
                    async for fragment in upstream:
                        for statement in parser.feed(fragment):
                            partial = {"status": "answered", "statements": [statement], "missing_information": []}
                            checked = validate_draft(json.dumps(partial, ensure_ascii=False), sources)
                            validate_scope(checked, route)
                            yield "statement", {"statement_index": index, "statement": checked.statements[0].model_dump()}
                            index += 1
                complete = parser.finish()
                draft = validate_draft(json.dumps(complete, ensure_ascii=False), sources)
                validate_scope(draft, route)
                if draft.status == "needs_clarification" and session["state"]["clarification_count"] >= 2 and not route.facts_with_message_ids:
                    draft.missing_information = ["关键事实仍不明确，可补充申请提交日期、资金具体用途或设备属性；也可以先仅了解一般条款。"]
                response = final_response(draft, sources, client.settings.model)
        response.elapsed_seconds = perf_counter() - started
        state = next_state(session, route, response, request.question)
        self.store.finish(cid, request.request_id, response.model_dump(), state, route.model_dump())
        yield "done", {"response": response.model_dump(), "route": {"intent": route.intent,
                        "resolved_product_id": route.resolved_product_id, "basis": route.basis}}
