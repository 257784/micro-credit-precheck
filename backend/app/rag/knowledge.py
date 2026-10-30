"""白名单政策读取和条款切分；预览不依赖模型或向量数据库。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import tempfile


from app.core.config import PROJECT_ROOT
ROOT = PROJECT_ROOT
PRODUCTS = {
    "working_capital": "经营周转贷（教学产品）",
    "equipment": "设备更新贷（教学产品）",
}
CHUNK_VERSION = "complete-clause-v1"
CLAUSE = re.compile(r"^## (第[一二三四五六七八九十百零〇0-9]+条)\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def project_path(relative: str, root: Path = ROOT) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"路径必须位于项目内：{relative}")
    return path


def load_config(path: Path | None = None) -> dict:
    if path is None:
        from app.rag.settings import knowledge_settings
        config = knowledge_settings()
    else:
        config = json.loads(path.read_text(encoding="utf-8"))
    for key in ("manifest", "model_dir", "chroma_dir", "output_dir"):
        project_path(config[key])
    if config["model_id"] != "BAAI/bge-m3" or config["dimension"] != 1024:
        raise ValueError("本轮仅配置 BGE-M3 的 1024 维向量")
    if not 1 <= config["max_tokens"] <= 8192 or config["batch_size"] < 1:
        raise ValueError("无效 token 上限或 batch_size")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,30}", config["collection_prefix"]):
        raise ValueError("集合前缀应为 3—31 位小写字母、数字或下划线")
    return config


def load_chunks(config: dict, root: Path = ROOT) -> tuple[list[Chunk], str]:
    """只读取 manifest 白名单，完整保留每条正文和条后例外说明。"""
    manifest_path = project_path(config["manifest"], root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("mode") != "offline_teaching"
            or manifest.get("status") != "teaching_draft"
            or manifest.get("fictional") is not True):
        raise ValueError("仅允许本轮明确标识的离线教学语料")
    corpus_root = (manifest_path.parent / "corpus").resolve()
    chunks: list[Chunk] = []
    seen_documents: set[str] = set()
    seen_paths: set[Path] = set()
    overrides = config.get("section_product_scopes", {})
    for document in manifest["documents"]:
        document_id = document["document_id"]
        source = (manifest_path.parent / document["path"]).resolve()
        if not source.is_relative_to(corpus_root) or not source.is_relative_to(root.resolve()):
            raise ValueError(f"白名单文件越出 corpus：{document_id}")
        if source.suffix != ".md" or not source.is_file():
            raise ValueError(f"缺少 Markdown 正文：{document_id}")
        if document_id in seen_documents or source in seen_paths:
            raise ValueError(f"重复文号或路径：{document_id}")
        seen_documents.add(document_id)
        seen_paths.add(source)
        text = source.read_text(encoding="utf-8")
        for label, value in (("文号", document_id), ("版本", document["version"])):
            if not re.search(rf"^\| {label} \| {re.escape(value)} \|$", text, re.MULTILINE):
                raise ValueError(f"正文与 manifest 的{label}不一致：{document_id}")
        matches = list(CLAUSE.finditer(text))
        if (not matches or len(matches) != document["clause_count"]
                or len(re.findall(r"^## ", text, re.MULTILINE)) != len(matches)):
            raise ValueError(f"条款数量或标题格式不符：{document_id}")
        clauses = [match.group(1) for match in matches]
        if len(set(clauses)) != len(clauses):
            raise ValueError(f"重复条号：{document_id}")
        document_overrides = overrides.get(document_id, {})
        if set(document_overrides) - set(clauses):
            raise ValueError(f"产品限定引用了不存在的条款：{document_id}")
        declared_products = document["product_scope"]
        if not declared_products or set(declared_products) - set(PRODUCTS.values()):
            raise ValueError(f"未知产品范围：{document_id}")
        inherited = [key for key, name in PRODUCTS.items() if name in declared_products]
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.end():end].strip()
            if not body:
                raise ValueError(f"空条款：{document_id} {match.group(1)}")
            products = document_overrides.get(match.group(1), inherited)
            if not products or not set(products).issubset(inherited):
                raise ValueError(f"条款产品范围不符合文档：{document_id} {match.group(1)}")
            metadata = {
                "document_id": document_id,
                "title": document["title"],
                "version": document["version"],
                "clause": match.group(1),
                "clause_title": match.group(2),
                "source_path": source.relative_to(root.resolve()).as_posix(),
                "source_line": text[:match.start()].count("\n") + 1,
                "dataset_id": manifest["dataset_id"],
                "status": manifest["status"],
                "mode": manifest["mode"],
                "fictional": True,
                "stage_scope": json.dumps(document["stage_scope"], ensure_ascii=False),
                **{f"applies_{key}": key in products for key in PRODUCTS},
            }
            passage = (
                f"{document['title']}（虚构教学拟定稿）\n"
                f"文号：{document_id}；版本：{document['version']}\n"
                f"适用产品：{'、'.join(PRODUCTS[key] for key in products)}\n"
                f"{match.group(1)} {match.group(2)}\n\n{body}"
            )
            chunk_id = digest([document_id, document["version"], match.group(1), passage])
            chunks.append(Chunk(chunk_id, passage, metadata))
    if not chunks:
        raise ValueError("白名单没有可入库条款")
    if set(overrides) - seen_documents:
        raise ValueError("产品限定引用了不存在的文档")
    signature = digest({
        "manifest": manifest, "chunks": [asdict(chunk) for chunk in chunks],
        "chunk_version": CHUNK_VERSION, "model_id": config["model_id"],
        "dimension": config["dimension"], "max_tokens": config["max_tokens"],
        "normalize": True, "distance": "cosine",
    })
    return chunks, signature


def write_json(path: Path, value: object) -> None:
    """先写临时文件再替换，避免活动索引记录只写了一半。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def product_filter(product: str) -> dict:
    if product not in PRODUCTS:
        raise ValueError("必须选择已知产品，不能混检不同产品的专属条款")
    return {"$and": [
        {f"applies_{product}": True}, {"status": "teaching_draft"},
        {"mode": "offline_teaching"},
    ]}
