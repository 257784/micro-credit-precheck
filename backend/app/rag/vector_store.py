"""本地 BGE-M3 与 Chroma；使用完整快照避免新旧政策块混杂。"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from app.rag.knowledge import Chunk, digest, product_filter, project_path, write_json


def model_fingerprint(directory: Path) -> str:
    """校验参与向量计算的文件指纹，防止同路径替换模型后混用旧索引。"""
    names = [
        "config.json", "config_sentence_transformers.json", "modules.json",
        "sentence_bert_config.json", "sentencepiece.bpe.model",
        "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json",
        "1_Pooling/config.json",
    ]
    weights = "model.safetensors" if (directory / "model.safetensors").is_file() else "pytorch_model.bin"
    names.append(weights)
    hasher = hashlib.sha256()
    for name in sorted(names):
        path = directory / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"模型文件缺失或为空：{path}")
        hasher.update(name.encode("utf-8"))
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                hasher.update(block)
    return hasher.hexdigest()


def open_client(config: dict):
    # 显式传入 embedding，关闭默认 embedding function，避免另下载模型。
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(
        path=str(project_path(config["chroma_dir"])),
        settings=Settings(anonymized_telemetry=False),
    )


def load_model(config: dict, device: str):
    import torch
    from sentence_transformers import SentenceTransformer

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA 不可用，请使用 --device cpu")
    model = SentenceTransformer(
        str(project_path(config["model_dir"])), device=device,
        local_files_only=True, trust_remote_code=False,
        model_kwargs={"torch_dtype": torch.float16 if device == "cuda" else torch.float32},
    )
    if model.get_sentence_embedding_dimension() != config["dimension"]:
        raise ValueError("模型输出维度与配置不一致")
    if config["max_tokens"] > model.max_seq_length:
        raise ValueError("配置长度超过模型实际支持长度")
    model.max_seq_length = config["max_tokens"]
    return model


def validate_vectors(vectors: list[list[float]], expected_count: int, dimension: int) -> None:
    if len(vectors) != expected_count:
        raise ValueError("向量数量与文本块数量不一致")
    for row in vectors:
        if len(row) != dimension or not all(math.isfinite(value) for value in row):
            raise ValueError("向量维度不符或包含非有限值")
        if abs(sum(value * value for value in row) - 1.0) > 0.02:
            raise ValueError("向量不是归一化非零向量")


def encode_texts(model, texts: list[str], config: dict) -> list[list[float]]:
    tokens = model.tokenizer(texts, add_special_tokens=True, truncation=False, padding=False)
    for index, sequence in enumerate(tokens["input_ids"]):
        if len(sequence) > config["max_tokens"]:
            raise ValueError(
                f"第 {index + 1} 个输入为 {len(sequence)} tokens，超过 "
                f"{config['max_tokens']}；已停止，未截断，请调整切分策略。"
            )
    vectors = model.encode(
        texts, batch_size=config["batch_size"], normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=True,
    ).astype("float32").tolist()
    validate_vectors(vectors, len(texts), config["dimension"])
    return vectors


def store_vectors(collection, chunks: list[Chunk], vectors: list[list[float]], dimension: int) -> None:
    validate_vectors(vectors, len(chunks), dimension)
    for start in range(0, len(chunks), 64):
        batch = chunks[start:start + 64]
        collection.upsert(
            ids=[chunk.id for chunk in batch],
            documents=[chunk.text for chunk in batch],
            metadatas=[chunk.metadata for chunk in batch],
            embeddings=vectors[start:start + 64],
        )
    if collection.count() != len(chunks):
        raise ValueError("写入后记录数不符，未激活该索引")


def ingest(config: dict, chunks: list[Chunk], corpus_signature: str, device: str) -> dict:
    from chromadb.errors import NotFoundError

    client = open_client(config)
    fingerprint = model_fingerprint(project_path(config["model_dir"]))
    signature = digest([corpus_signature, fingerprint])
    name = config["collection_prefix"] + "_" + signature[:24]
    collection = None
    try:
        collection = client.get_collection(name=name, embedding_function=None)
    except NotFoundError:
        pass
    reused = bool(
        collection is not None and (collection.metadata or {}).get("complete") is True
        and collection.metadata.get("signature") == signature
        and collection.count() == len(chunks)
    )
    if not reused:
        model = load_model(config, device)
        vectors = encode_texts(model, [chunk.text for chunk in chunks], config)
        collection = client.get_or_create_collection(
            name=name, embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"signature": signature, "complete": False, "dimension": config["dimension"]},
        )
        store_vectors(collection, chunks, vectors, config["dimension"])
        collection.modify(metadata={
            "signature": signature, "complete": True, "dimension": config["dimension"],
        })
    state = {
        "collection": name, "signature": signature, "corpus_signature": corpus_signature,
        "model_fingerprint": fingerprint, "count": len(chunks),
        "model_id": config["model_id"], "dimension": config["dimension"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # 只在所有向量成功保存且计数正确后切换；失败时保留上一次活动索引。
    write_json(project_path(config["output_dir"]) / "active-index.json", state)
    return {**state, "reused": reused}


def active_collection(config: dict, corpus_signature: str):
    state_path = project_path(config["output_dir"]) / "active-index.json"
    if not state_path.is_file():
        raise ValueError("尚无活动索引，请先执行 ingest")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["corpus_signature"] != corpus_signature:
        raise ValueError("语料或配置已变化，请重新 ingest；未查询旧索引")
    client = open_client(config)
    collection = client.get_collection(name=state["collection"], embedding_function=None)
    metadata = collection.metadata or {}
    if (not metadata.get("complete") or metadata.get("signature") != state["signature"]
            or collection.count() != state["count"]):
        raise ValueError("活动索引不完整或已被修改，请重新 ingest")
    return client, collection, state


def query(config: dict, corpus_signature: str, question: str, product: str, top_k: int, device: str) -> list:
    if not question.strip() or not 1 <= top_k <= 20:
        raise ValueError("问题不能为空，top-k 必须为 1—20")
    where = product_filter(product)
    return query_filtered(config, corpus_signature, question, where, top_k, device)


def query_filtered(config: dict, corpus_signature: str, question: str, where: dict,
                   top_k: int = 8, device: str = "cpu") -> list:
    """内部受控过滤入口；对话客户端不能直接提供 where。"""
    if not question.strip() or not 1 <= top_k <= 20:
        raise ValueError("问题不能为空，top-k 必须为 1—20")
    client, collection, state = active_collection(config, corpus_signature)
    if model_fingerprint(project_path(config["model_dir"])) != state["model_fingerprint"]:
        raise ValueError("本地模型已变化，请重新 ingest")
    model = load_model(config, device)
    vector = encode_texts(model, [question.strip()], config)
    result = collection.query(
        query_embeddings=vector, where=where, n_results=min(top_k, state["count"]),
        include=["documents", "metadatas", "distances"],
    )
    return [
        {"id": chunk_id, "text": text, "metadata": metadata,
         "cosine_distance": distance}
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0],
            result["metadatas"][0], result["distances"][0],
        )
    ]
