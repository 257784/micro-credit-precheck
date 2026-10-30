"""本地条款重排序；整批评分成功才换序，失败保留可追溯的向量候选。"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from app.rag.knowledge import project_path

MODEL_ID = "BAAI/bge-reranker-v2-m3"
FILES = (
    "config.json", "model.safetensors", "sentencepiece.bpe.model",
    "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
)


def load_config(path: Path) -> dict:
    """独立配置不参与向量快照签名，切换重排设置不需要重新入库。"""
    config = json.loads(path.read_text(encoding="utf-8"))
    project_path(config["model_dir"])
    if config["model_id"] != MODEL_ID:
        raise ValueError("本轮仅支持 bge-reranker-v2-m3")
    for key, maximum in (("max_tokens", 8192), ("batch_size", 32)):
        if type(config[key]) is not int or not 1 <= config[key] <= maximum:
            raise ValueError(f"{key} 必须为 1—{maximum} 的整数")
    return config


def fingerprint(directory: Path) -> str:
    """完整读取模型文件，便于对比报告追溯到实际本地模型。"""
    hasher = hashlib.sha256()
    for name in FILES:
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"重排模型文件缺失或为空：{name}")
        hasher.update(name.encode("utf-8"))
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                hasher.update(block)
    return hasher.hexdigest()


class LocalReranker:
    """按需加载，单实例复用模型；CPU 单精度，CUDA 半精度，禁止自动下载。"""

    def __init__(self, config: dict, device: str = "cpu") -> None:
        if device not in ("cpu", "cuda"):
            raise ValueError("重排设备只能是 cpu 或 cuda")
        self.config = config
        self.device = device
        self.model = None
        self.tokenizer = None
        self.model_fingerprint = None

    def _load(self) -> None:
        if self.model is not None:
            return
        directory = project_path(self.config["model_dir"])
        model_hash = fingerprint(directory)
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA 不可用，请使用 cpu")
        tokenizer = AutoTokenizer.from_pretrained(
            str(directory), local_files_only=True, trust_remote_code=False,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            str(directory), local_files_only=True, trust_remote_code=False,
        )
        # XLM-R 的位置编码包含 padding 偏移，使用 tokenizer 声明的输入上限校验。
        if self.config["max_tokens"] > tokenizer.model_max_length:
            raise ValueError("重排配置长度超过 tokenizer 支持上限")
        model = model.half() if self.device == "cuda" else model.float()
        model = model.to(self.device).eval()
        self.tokenizer, self.model = tokenizer, model
        self.model_fingerprint = model_hash

    def score(self, question: str, texts: list[str]) -> list[float]:
        """问题与条款合计长度含特殊 token；超长整批拒绝，不丢弃例外条件。"""
        self._load()
        import torch

        pairs = [(question, text) for text in texts]
        tokenized = self.tokenizer(pairs, truncation=False, padding=False)
        for index, tokens in enumerate(tokenized["input_ids"]):
            if len(tokens) > self.config["max_tokens"]:
                raise ValueError(
                    f"重排第 {index + 1} 对输入为 {len(tokens)} tokens，超过 "
                    f"{self.config['max_tokens']}，未截断"
                )
        scores = []
        batch_size = self.config["batch_size"]
        for start in range(0, len(pairs), batch_size):
            inputs = self.tokenizer(
                pairs[start:start + batch_size], truncation=False,
                padding=True, return_tensors="pt",
            )
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with torch.inference_mode():
                batch = self.model(**inputs, return_dict=True).logits.view(-1)
                scores.extend(batch.float().cpu().tolist())
        return scores


def rerank_candidates(
    question: str, candidates: list[dict], context_k: int, scorer: LocalReranker,
) -> dict:
    """保留所有候选和原始排名；故障回退也只选前 context_k 条供后续使用。"""
    if not question.strip() or type(context_k) is not int or not 1 <= context_k <= 20:
        raise ValueError("问题不能为空，context-k 必须为 1—20 的整数")
    original = [
        {**deepcopy(item), "vector_rank": rank, "rerank_score": None, "rerank_rank": None}
        for rank, item in enumerate(candidates, start=1)
    ]
    ranked = deepcopy(original)
    status, error = "empty", None
    started = perf_counter()
    if candidates:
        try:
            scores = scorer.score(question.strip(), [item["text"] for item in original])
            if len(scores) != len(original) or not all(math.isfinite(s) for s in scores):
                raise ValueError("重排分数数量不符或包含非有限值")
            for item, score in zip(ranked, scores):
                item["rerank_score"] = float(score)
            # 同分时保留原始向量排名；任何评分失败均不应用部分新分数。
            ranked.sort(key=lambda item: -item["rerank_score"])
            for rank, item in enumerate(ranked, start=1):
                item["rerank_rank"] = rank
            status = "success"
        except (OSError, ImportError, RuntimeError, ValueError, TypeError) as failure:
            ranked = deepcopy(original)
            status = "fallback"
            error = {"type": type(failure).__name__, "message": str(failure)}
    return {
        "status": status, "error": error, "context_k": context_k,
        "candidate_count": len(original), "elapsed_seconds": perf_counter() - started,
        "original_results": original, "ranked_results": ranked,
        "results": ranked[:context_k],
    }
