"""用固定开发题比较 Top-K；只读当前索引，不下载模型或生成业务答案。"""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.knowledge import digest, load_chunks, load_config, product_filter, project_path, write_json

DEFAULT_CASES = ROOT / "docs/f3-knowledge-base/management/retrieval-cases.json"
KS = [1, 3, 5, 8, 10, 15, 20]


def clause_key(metadata: dict) -> tuple:
    """条款引用包含版本，避免不同版本被误判为命中。"""
    return tuple(metadata[key] for key in ("document_id", "clause", "version"))


def validate_cases(dataset: dict, chunks: list) -> list:
    """标签必须指向当前产品可检索的真实条款。"""
    cases = dataset["cases"]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("测试集为空或用例编号重复")
    known = {clause_key(chunk.metadata): chunk.metadata for chunk in chunks}
    positives = 0
    for case in cases:
        product_filter(case["product"])
        if not case["question"].strip():
            raise ValueError("测试问题不能为空")
        labels = [tuple(label) for label in case["relevant"]]
        if len(set(labels)) != len(labels):
            raise ValueError(f"重复标签：{case['id']}")
        for label in labels:
            if label not in known or not known[label][f"applies_{case['product']}"]:
                raise ValueError(f"标签不存在或产品不适用：{case['id']} {label}")
        positives += bool(labels)
    if not positives:
        raise ValueError("至少需要一道有依据的正例题")
    return cases


def summarize(cases: list, rankings: dict, ks: list[int]) -> dict:
    """所有 K 使用同一最大召回列表的前缀；负例不进入 Recall 分母。"""
    if not ks or ks != sorted(set(ks)) or ks[0] < 1:
        raise ValueError("K 必须为递增正整数")
    positives = [case for case in cases if case["relevant"]]
    if not positives:
        raise ValueError("没有可计算召回率的正例")
    rows, details = [], []
    for k in ks:
        recalls, hits, complete, sizes, chars = [], [], [], [], []
        for case in cases:
            candidates = rankings[case["id"]][:k]
            expected = {tuple(label) for label in case["relevant"]}
            found = {clause_key(item["metadata"]) for item in candidates}
            missing = sorted(expected - found)
            detail = {"case_id": case["id"], "k": k, "returned": len(candidates),
                      "missing": missing, "recall": None}
            if expected:
                recall = len(expected & found) / len(expected)
                recalls.append(recall)
                hits.append(bool(expected & found))
                complete.append(not missing)
                sizes.append(len(candidates))
                chars.append(sum(len(item["text"]) for item in candidates))
                detail["recall"] = recall
            details.append(detail)
        rows.append({
            "k": k, "recall": sum(recalls) / len(positives),
            "hit_rate": sum(hits) / len(positives),
            "all_evidence_rate": sum(complete) / len(positives),
            "mean_returned": sum(sizes) / len(positives),
            "mean_context_chars": sum(chars) / len(positives),
        })
    # 目标是开发集全部标注依据被覆盖；不以最大 K 的高分替代最小可用 K。
    suggested = next((row["k"] for row in rows if row["all_evidence_rate"] == 1), None)
    return {"positive_cases": len(positives), "negative_cases": len(cases) - len(positives),
            "metrics": rows, "suggested_k": suggested, "details": details}


def retrieve(
    config: dict, signature: str, cases: list, device: str, retrieval_k: int = 20,
) -> tuple:
    """模型只加载一次，批量编码问题，每题只执行一次最大 K 查询。"""
    if not 1 <= retrieval_k <= 20:
        raise ValueError("retrieval_k 必须为 1—20")
    from app.rag import vector_store

    client, collection, state = vector_store.active_collection(config, signature)
    if vector_store.model_fingerprint(project_path(config["model_dir"])) != state["model_fingerprint"]:
        raise ValueError("模型已变化，请先重新入库")
    started = perf_counter()
    model = vector_store.load_model(config, device)
    vectors = vector_store.encode_texts(model, [case["question"] for case in cases], config)
    encoding_seconds = perf_counter() - started
    rankings, query_seconds = {}, {}
    for case, vector in zip(cases, vectors):
        print(f"检索 {case['id']}…", flush=True)
        started = perf_counter()
        result = collection.query(
            query_embeddings=[vector], where=product_filter(case["product"]),
            n_results=min(retrieval_k, state["count"]),
            include=["documents", "metadatas", "distances"],
        )
        query_seconds[case["id"]] = perf_counter() - started
        rankings[case["id"]] = [
            {"id": item_id, "text": text, "metadata": metadata, "cosine_distance": distance}
            for item_id, text, metadata, distance in zip(
                result["ids"][0], result["documents"][0],
                result["metadatas"][0], result["distances"][0],
            )
        ]
    return rankings, {"index": state, "encoding_seconds": encoding_seconds,
                      "max_k_query_seconds": query_seconds}


def markdown_report(report: dict) -> str:
    lines = ["# Top-K 开发集测试结果", "", f"运行时间：{report['run_at']}", "",
             "同一次最大 K 召回的前缀对比；不是分别运行各 K 的性能基准。",
             "", "| K | 宏平均 Recall | Hit | 全依据覆盖率 | 平均返回数 | 平均正文字符数 |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in report["metrics"]:
        lines.append(
            f"| {row['k']} | {row['recall']:.2%} | {row['hit_rate']:.2%} | "
            f"{row['all_evidence_rate']:.2%} | {row['mean_returned']:.1f} | "
            f"{row['mean_context_chars']:.0f} |"
        )
    suggested = report["suggested_k"]
    lines += ["", f"开发集建议 K：{suggested if suggested else '未选定，最大 K 仍有依据漏召回'}。",
              "这是固定开发题的经验结果，不保证未知问题召回率；标签需人工复核。",
              "无依据题不计召回率；Top-K 返回候选不代表系统已识别无依据或完成拒答。",
              "未标注条款可能同样相关，因此不将标签外结果直接计为错误。", "",
              "## 各 K 的漏召回", ""]
    for detail in report["details"]:
        if detail["missing"]:
            labels = "; ".join(" ".join(label) for label in detail["missing"])
            lines.append(f"- K={detail['k']} / {detail['case_id']}：{labels}")
    lines += ["", "逐题问题、标签、候选正文、距离及运行指纹见同目录 report.json。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        chunks, signature = load_chunks(config)
        dataset = json.loads(args.cases.read_text(encoding="utf-8"))
        cases = validate_cases(dataset, chunks)
        if args.validate_only:
            print(f"标签校验通过：{len(cases)} 题，K={KS}；尚未执行真实检索。")
            return 0
        rankings, runtime = retrieve(config, signature, cases, args.device)
        report = {**summarize(cases, rankings, KS), **runtime,
                  "run_at": datetime.now(timezone.utc).isoformat(),
                  "corpus_signature": signature, "dataset_signature": digest(dataset),
                  "method": "one_max_k_query_then_prefix", "device": args.device,
                  "packages": {name: version(name) for name in
                               ("chromadb", "sentence-transformers", "torch")},
                  "dataset": dataset, "rankings": rankings}
        output = project_path(config["output_dir"]) / "top-k-evaluation"
        write_json(output / "report.json", report)
        (output / "report.md").write_text(markdown_report(report), encoding="utf-8")
        print(markdown_report(report))
        print(f"报告：{output}")
        return 0
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as error:
        print(f"评测失败（{type(error).__name__}）：{error}", file=sys.stderr)
        print("本次未生成成功报告；已有报告可能属于旧运行，请核对 run_at。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
