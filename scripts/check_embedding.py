"""检查本地 BGE-M3 文件，并使用后端环境验证短文本向量。"""

import argparse
import importlib.util
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--check-files", action="store_true", help="只检查本地文件，不加载模型")
    args = parser.parse_args()

    # 本脚本位于项目根目录的 scripts 下。
    project_root = Path(__file__).resolve().parents[1]
    model_dir = project_root / "models" / "bge-m3"
    required_files = [
        "config.json",
        "config_sentence_transformers.json",
        "modules.json",
        "sentence_bert_config.json",
        "sentencepiece.bpe.model",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "1_Pooling/config.json",
    ]
    missing_files = [
        name for name in required_files
        if not (model_dir / name).is_file() or (model_dir / name).stat().st_size == 0
    ]
    if not any(
        (model_dir / name).is_file() and (model_dir / name).stat().st_size > 0
        for name in ("pytorch_model.bin", "model.safetensors")
    ):
        missing_files.append("pytorch_model.bin 或 model.safetensors")

    print("Python：", sys.executable)
    print("模型目录：", model_dir)
    if missing_files:
        print("缺少或为空的模型文件：")
        for name in missing_files:
            print("  -", name)

    if args.check_files:
        if missing_files:
            raise SystemExit(1)
        print("关键文件存在；此检查不验证下载哈希，仍需执行模型加载检查。")
        return

    missing_packages = [
        name for name in ("torch", "sentence_transformers")
        if importlib.util.find_spec(name) is None
    ]
    if missing_packages:
        print("当前 Python 缺少模块：", ", ".join(missing_packages))
        print("请在项目根目录运行：")
        print(r".\backend\.venv\Scripts\python.exe scripts/check_embedding.py --device cpu")
    if missing_packages or missing_files:
        raise SystemExit(1)

    # 文件与环境检查通过后再加载依赖；不会自动下载模型。
    import torch
    from sentence_transformers import SentenceTransformer

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("当前 PyTorch 无法使用 CUDA，请先使用 CPU 检查。")

    # GPU 使用半精度降低显存占用；CPU 使用单精度。
    dtype = torch.float16 if args.device == "cuda" else torch.float32

    model = SentenceTransformer(
        str(model_dir),
        device=args.device,
        local_files_only=True,
        model_kwargs={"torch_dtype": dtype},
    )

    # 只用于这次短文本检查，不代表后续文档切分长度。
    model.max_seq_length = 512

    documents = [
        "设备采购尚未签订合同时，可提交符合要求的报价单及未签约说明。",
        "经营收入佐证原则上覆盖申请提交月份之前最近三个完整自然月。",
    ]
    question = "没有签订设备采购合同，可以用报价单吗？"

    document_vectors = model.encode(
        documents,
        batch_size=1,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")

    question_vector = model.encode(
        [question],
        batch_size=1,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype("float32")[0]

    # 归一化向量的点积对应余弦相似度。
    scores = document_vectors @ question_vector

    print("运行设备：", args.device)
    print("文档向量形状：", document_vectors.shape)
    print("问题向量形状：", question_vector.shape)

    for index in scores.argsort()[::-1]:
        print(f"相似度 {scores[index]:.4f}：{documents[index]}")


if __name__ == "__main__":
    main()
