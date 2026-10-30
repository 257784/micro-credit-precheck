"""在用户本机显式执行 DeepSeek 问答评测；每题最多一次生成调用。"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.llm.deepseek import DeepSeekClient, Settings
from app.rag.knowledge import digest, load_chunks, load_config, project_path, write_json
from app.schemas.policy import QuestionRequest
from app.services.policy import PolicyQA
from evals.runners.evaluate_retrieval import DEFAULT_CASES, retrieve, validate_cases


def evaluate_case(case: dict, result) -> dict:
    """引用覆盖只是观测项；引用相关性和答案完整性留人工判断。"""
    cited = {source.source_id: source for source in result.sources}
    references = {
        (source.document_id, source.clause, source.version)
        for source_id in result.cited_source_ids if (source := cited.get(source_id)) is not None
    }
    expected = {tuple(label) for label in case["relevant"]}
    return {
        "case_id": case["id"], "question": case["question"], "product": case["product"],
        "expected_references": case["relevant"], "response": result.model_dump(),
        "reference_coverage": len(expected & references) / len(expected) if expected else None,
        "citation_validation": "passed" if result.statements else "not_applicable",
        "manual_review": {"answer_correct": None, "conditions_complete": None,
                          "citations_support_claims": None, "scope_respected": None,
                          "reason": "待人工逐项核对，不由引用匹配自动评分"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="显式执行，可能产生DeepSeek API费用")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--rerank", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 16:
        parser.error("limit 必须为1—16")
    config = load_config()
    chunks, signature = load_chunks(config)
    dataset = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    cases = validate_cases(dataset, chunks)[:args.limit]
    if not args.run:
        print(f"已校验 {len(cases)} 题；加 --run 才会调用 DeepSeek。建议先逐题页面验证。")
        return 0
    # 配置存在后再加载大模型依赖；不记录凭据或配置对象 repr。
    settings = Settings.from_environment()
    rankings, runtime = retrieve(config, signature, cases, "cpu", retrieval_k=8)
    service = PolicyQA(client_factory=lambda: DeepSeekClient(settings))
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "model": settings.model,
              "corpus_signature": signature, "dataset_signature": digest(dataset),
              "rerank": args.rerank, "retrieval_runtime": runtime,
              "status": "running", "cases": []}
    output = project_path(config["output_dir"]) / "policy-qa-evaluation"
    for case in cases:
        service.retriever = lambda question, product, rows=rankings[case["id"]]: rows
        result = service.answer(QuestionRequest(question=case["question"], product=case["product"],
                                               rerank=args.rerank))
        report["cases"].append(evaluate_case(case, result))
        write_json(output / "report.json", report)
        print(f"{case['id']}: {result.status}", flush=True)
    report["status"] = "incomplete" if any(
        row["response"]["status"].endswith("_error") for row in report["cases"]
    ) else "complete_pending_manual_review"
    write_json(output / "report.json", report)
    lines = ["# 政策问答人工验收", "", f"状态：{report['status']}",
             "引用匹配通过不代表回答正确，须核对下列回答、条件和原文。", ""]
    for row in report["cases"]:
        response = row["response"]
        lines += [f"## {row['case_id']} {row['question']}", "", f"状态：{response['status']}",
                  "", response["answer"], "", "待补充：" + "；".join(response["missing_information"]), ""]
        for statement in response["statements"]:
            for evidence in statement["evidence"]:
                lines += [f"- [{evidence['source_id']}] 原文：{evidence['quote']}"]
        lines += ["", "本次候选出处："]
        for source in response["sources"]:
            cited_label = "已引用" if source["source_id"] in response["cited_source_ids"] else "候选"
            lines += [f"- [{source['source_id']}] {source['document_id']} / {source['version']} / "
                      f"{source['clause']}（{cited_label}），{source['source_path']}:{source['source_line']}"]
        lines += ["", "- 人工检查：答案正确 / 条件完整 / 引用支持解释 / 未越权：待填写", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"报告：{output}")
    return 1 if report["status"] == "incomplete" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # 不输出可能包含认证上下文的第三方 traceback。
        print("问答评测未完成，请检查本机依赖、索引及 DeepSeek 环境设置；没有据此判定通过。", file=sys.stderr)
        raise SystemExit(1)
