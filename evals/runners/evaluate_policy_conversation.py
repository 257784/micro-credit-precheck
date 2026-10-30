"""多轮HTTP验收；默认只校验计划，--run 才访问本机后端并可能调用付费模型。"""

import argparse
import asyncio
import json
from pathlib import Path
import sys
from time import perf_counter
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.knowledge import write_json


async def evaluate(dataset: dict, limit: int) -> dict:
    import httpx

    report = {"run_at": datetime.now(timezone.utc).isoformat(), "mode": "real_local_backend",
              "status": "running", "cases": []}
    output = ROOT / "backend/.data/knowledge-base/conversation-evaluation"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=150) as client:
        for case in dataset["cases"][:limit]:
            created = await client.post("/api/policy/conversations")
            created.raise_for_status()
            cid = created.json()["conversation_id"]
            record = {"id": case["id"], "check": case["check"], "turns": [],
                      "manual_review": {"scope_correct": None, "clarification_necessary": None,
                                        "answer_complete": None, "citations_support": None, "reason": "待人工核对"}}
            report["cases"].append(record)
            try:
                for index, question in enumerate(case["turns"]):
                    from uuid import uuid4

                    rid = uuid4().hex
                    started = perf_counter()
                    trace = {"question": question, "events": [], "first_status_seconds": None,
                             "first_statement_seconds": None, "done_seconds": None}
                    record["turns"].append(trace)
                    async with client.stream("POST", f"/api/policy/conversations/{cid}/messages/stream",
                                             json={"question": question, "request_id": rid}) as response:
                        response.raise_for_status()
                        kind = "message"
                        async for line in response.aiter_lines():
                            if line.startswith("event: "):
                                kind = line[7:]
                            elif line.startswith("data: "):
                                data = json.loads(line[6:])
                                elapsed = perf_counter() - started
                                trace["events"].append({"event": kind, "seconds": elapsed, "data": data})
                                for event, field in (("status", "first_status_seconds"),
                                                     ("statement", "first_statement_seconds"), ("done", "done_seconds")):
                                    if kind == event and trace[field] is None:
                                        trace[field] = elapsed
                    snapshot = await client.get(f"/api/policy/conversations/{cid}")
                    snapshot.raise_for_status()
                    trace["server_turn"] = snapshot.json()["turns"][-1]
                    print(f"{case['id']} 第{index + 1}轮：{trace['server_turn']['status']}", flush=True)
                    write_json(output / "report.json", report)
                    if trace["done_seconds"] is None:
                        break
            finally:
                await client.delete(f"/api/policy/conversations/{cid}")
    report["status"] = "complete_pending_manual_review" if all(
        len(case["turns"]) == len(source["turns"]) and all(t["done_seconds"] is not None for t in case["turns"])
        for case, source in zip(report["cases"], dataset["cases"])
    ) else "incomplete"
    write_json(output / "report.json", report)
    lines = ["# 多轮真实HTTP验收记录", "", f"状态：{report['status']}",
             "这是运行完成状态，不是答案质量评分；下列项目需要人工核对。", ""]
    for case in report["cases"]:
        lines += [f"## {case['id']}", "", case["check"], ""]
        for index, turn in enumerate(case["turns"]):
            lines += [f"### 第{index + 1}轮：{turn['question']}", "",
                      f"首要点：{turn['first_statement_seconds']}秒；done：{turn['done_seconds']}秒", ""]
            response = turn["server_turn"].get("response")
            lines += [response["answer"] if response else "本轮未完成", ""]
        lines += ["人工复核：范围 / 追问必要性 / 回答完整性 / 引用支持：待填写", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"报告：{output}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    dataset = json.loads((ROOT / "docs/f3-knowledge-base/management/conversation-cases.json").read_text(encoding="utf-8"))
    if not 1 <= args.limit <= len(dataset["cases"]):
        parser.error("limit超出用例范围")
    if not args.run:
        print(f"已读取{len(dataset['cases'])}段多轮用例；默认不调用API。先启动本机后端，再加 --run --limit 8 执行。")
        return 0
    report = asyncio.run(evaluate(dataset, args.limit))
    return 1 if report["status"] == "incomplete" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("多轮验收未完成，请检查本机后端和环境；已有JSON可能只有部分轮次，不判定通过。", file=sys.stderr)
        raise SystemExit(1)
