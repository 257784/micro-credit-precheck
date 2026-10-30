"""政策语料预览、向量入库和本地检索；从任意工作目录执行。"""

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.knowledge import PRODUCTS, load_chunks, load_config, project_path, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "ingest", "query", "status"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", type=Path, default=None, help="可选外部JSON配置；默认使用Python配置")
        if name in ("ingest", "query"):
            command.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
        if name == "query":
            command.add_argument("--text", required=True)
            command.add_argument("--product", choices=list(PRODUCTS), required=True)
            command.add_argument("--top-k", type=int, default=8)
            command.add_argument("--rerank", action="store_true")
            command.add_argument("--context-k", type=int)
            command.add_argument("--reranker-device", choices=["cpu", "cuda"], default="cpu")
            command.add_argument(
                "--reranker-config", type=Path, default=ROOT / "backend/reranker.json",
            )
    args = parser.parse_args()
    try:
        if args.command == "query":
            if args.context_k is not None and not args.rerank:
                raise ValueError("--context-k 需要同时使用 --rerank")
            context_k = 5 if args.context_k is None else args.context_k
            if args.rerank and not 1 <= context_k <= args.top_k <= 20:
                raise ValueError("需要 1 <= context-k <= top-k <= 20")
        config = load_config(args.config)
        chunks, signature = load_chunks(config)
        if args.command == "preview":
            output = project_path(config["output_dir"]) / "chunks.json"
            write_json(output, {"corpus_signature": signature, "chunks": [asdict(c) for c in chunks]})
            counts = Counter(c.metadata["document_id"] for c in chunks)
            print(json.dumps({"documents": dict(counts), "chunks": len(chunks),
                              "output": str(output)}, ensure_ascii=False, indent=2))
            return 0

        from app.rag import vector_store

        if args.command == "ingest":
            print("正在校验本地模型并写入向量；模型指纹校验可能需要一些时间。", flush=True)
            result = vector_store.ingest(config, chunks, signature, args.device)
        elif args.command == "status":
            client, collection, state = vector_store.active_collection(config, signature)
            result = {**state, "persisted_count": collection.count()}
        else:
            result = {"notice": "以下仅为虚构教学候选条款；距离不是置信度，也不代表政策符合或审批结论。",
                      "results": vector_store.query(
                          config, signature, args.text, args.product, args.top_k, args.device,
                      )}
            if args.rerank:
                from app.rag import reranker

                # 配置错误是用户输入错误；模型加载和评分故障才进入降级。
                settings = reranker.load_config(args.reranker_config)
                scorer = reranker.LocalReranker(settings, args.reranker_device)
                outcome = reranker.rerank_candidates(
                    args.text, result["results"], context_k, scorer,
                )
                result["results"] = outcome.pop("results")
                result["reranking"] = {
                    **outcome, "model_id": settings["model_id"],
                    "model_fingerprint": scorer.model_fingerprint,
                    "score_type": "raw_logit_higher_is_more_relevant",
                    "device": args.reranker_device,
                }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as error:
        print(f"执行失败（{type(error).__name__}）：{error}", file=sys.stderr)
        print("请使用 backend/.venv/Scripts/python.exe，并检查文件、依赖与权限。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
