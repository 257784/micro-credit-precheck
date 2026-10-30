"""实际召回同一批候选，比较向量原序与本地重排的 Top-3/5 覆盖。"""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.knowledge import digest, load_chunks, load_config, project_path, write_json
from app.rag.reranker import LocalReranker, load_config as load_reranker_config, rerank_candidates
from evals.runners.evaluate_retrieval import DEFAULT_CASES, retrieve, summarize, validate_cases


def compare(cases: list, rankings: dict, scorer: LocalReranker) -> dict:
    """失败题保留降级证据，从两侧效果对比中同时排除，避免虚报模型效果。"""
    outcomes, reranked, successful = {}, {}, []
    for case in cases:
        outcome = rerank_candidates(case["question"], rankings[case["id"]], 5, scorer)
        outcomes[case["id"]] = outcome
        reranked[case["id"]] = outcome["ranked_results"]
        if outcome["status"] in ("success", "empty"):
            successful.append(case)
    has_positive = any(case["relevant"] for case in successful)
    comparison = None
    if has_positive:
        comparison = {
            "vector": summarize(successful, rankings, [3, 5]),
            "reranked": summarize(successful, reranked, [3, 5]),
        }
    failed = [case_id for case_id, result in outcomes.items() if result["status"] == "fallback"]
    return {
        "status": "incomplete" if failed else "complete",
        "failed_cases": failed, "comparison_case_ids": [case["id"] for case in successful],
        "comparison": comparison, "outcomes": outcomes,
        "vector_all_cases": summarize(cases, rankings, [3, 5, 8]),
    }


def markdown_report(report: dict) -> str:
    lines = ["# 重排序小规模对比", "", f"运行时间：{report['run_at']}",
             f"状态：{report['status']}；失败题：{report['failed_cases']}", "",
             "每题实际查询 K=8，再在同一候选池中重排；不能补回候选外的依据。",
             "失败题从对比两侧同时排除；失败详情和原排名仍保留在 JSON。", ""]
    comparison = report["comparison"]
    if comparison is None:
        lines += ["没有可用于重排效果对比的成功正例，不作效果结论。", ""]
    else:
        lines += [f"参与对比：{len(report['comparison_case_ids'])} 题（含无依据题，指标只计正例）。",
                  "", "| 方式 | Top-K | Recall | Hit | 全依据覆盖率 | 平均字符数 |",
                  "| --- | --- | --- | --- | --- | --- |"]
        for mode in ("vector", "reranked"):
            for row in comparison[mode]["metrics"]:
                lines.append(
                    f"| {mode} | {row['k']} | {row['recall']:.2%} | "
                    f"{row['hit_rate']:.2%} | {row['all_evidence_rate']:.2%} | "
                    f"{row['mean_context_chars']:.0f} |"
                )
        lines += ["", "## 逐题召回变化（重排后减去重排前）", "",
                  "| 题号 | Top-K | Recall 变化 | 重排后漏召回 |", "| --- | --- | --- | --- |"]
        for before, after in zip(comparison["vector"]["details"], comparison["reranked"]["details"]):
            if before["recall"] is None:
                continue
            change = after["recall"] - before["recall"]
            missing = "; ".join(" ".join(label) for label in after["missing"]) or "无"
            lines.append(f"| {before['case_id']} | {before['k']} | {change:+.2%} | {missing} |")
    times = [outcome["elapsed_seconds"] for outcome in report["outcomes"].values()
             if outcome["status"] == "success"]
    if times:
        lines += ["", f"成功重排耗时总计：{sum(times):.3f}s；均值：{sum(times) / len(times):.3f}s。",
                  "首次包含模型文件校验及冷加载，后续复用模型；这是单次运行观察，不是延迟基准。"]
    lines += ["", "原始 logit 越高代表模型判断越相关，不是正确率；未设置分数阈值。",
              "无依据题只列候选，尚未实现生成回答、拒答或权限防护。",
              "逐题全文、来源、两种排名、分数与错误见 report.json；小样本结果需人工复核。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--reranker-config", type=Path, default=ROOT / "backend/reranker.json")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--reranker-device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        settings = load_reranker_config(args.reranker_config)
        chunks, signature = load_chunks(config)
        dataset = json.loads(args.cases.read_text(encoding="utf-8"))
        cases = validate_cases(dataset, chunks)
        if args.validate_only:
            print(f"配置与 {len(cases)} 题标签校验通过；未运行真实模型或检索。")
            return 0
        rankings, runtime = retrieve(config, signature, cases, args.device, retrieval_k=8)
        scorer = LocalReranker(settings, args.reranker_device)
        print("开始本地重排序，首次读取权重并加载模型可能需要等待。", flush=True)
        report = {
            **compare(cases, rankings, scorer), "retrieval_runtime": runtime,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_k": 8, "context_ks": [3, 5],
            "corpus_signature": signature, "dataset_signature": digest(dataset),
            "reranker": {"config": settings, "device": args.reranker_device,
                         "model_fingerprint": scorer.model_fingerprint},
            "dataset": dataset,
            "packages": {name: version(name) for name in ("torch", "transformers", "chromadb")},
        }
        output = project_path(config["output_dir"]) / "reranker-evaluation"
        write_json(output / "report.json", report)
        (output / "report.md").write_text(markdown_report(report), encoding="utf-8")
        print(markdown_report(report))
        print(f"报告：{output}")
        return 0 if report["status"] == "complete" else 1
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as error:
        print(f"对比未完成（{type(error).__name__}）：{error}", file=sys.stderr)
        print("本次未生成完整对比报告；旧报告请核对 run_at。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
