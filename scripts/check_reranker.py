import argparse
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    model_dir = root / "models" / "bge-reranker-v2-m3"

    required = [
        "config.json",
        "model.safetensors",
        "sentencepiece.bpe.model",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
    ]
    missing = [
        name for name in required
        if not (model_dir / name).is_file()
        or (model_dir / name).stat().st_size == 0
    ]
    if missing:
        raise SystemExit(f"模型文件缺失或为空：{missing}")

    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA 不可用，请先使用 --device cpu")

    print("模型目录：", model_dir)
    print("运行设备：", args.device)

    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir),
        local_files_only=True,
        trust_remote_code=False,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir),
        local_files_only=True,
        trust_remote_code=False,
    )
    if args.device == "cuda":
        model = model.half()
    else:
        model = model.float()
    model = model.to(args.device).eval()

    # 故意将相关文本放在第二位，观察模型能否将其排到前面。
    passages = [
        "经营收入佐证原则上覆盖申请月份之前最近三个完整自然月。",
        "尚未签订设备采购合同的，可提交符合要求的供应商报价单及未签约说明。",
        "人工复核意见应记录核对的材料版本、政策依据和待解决事项。",
    ]
    questions = [
        "没有签设备采购合同，可以用报价单吗？",
        "经营收入资料需要覆盖多久？",
    ]

    for question in questions:
        pairs = [(question, passage) for passage in passages]
        inputs = tokenizer(
            pairs,
            padding=True,
            truncation=False,
            return_tensors="pt",
        )

        # 本次只测试短文本；避免静默截断造成条件丢失。
        if inputs["input_ids"].shape[1] > 512:
            raise ValueError("测试输入超过 512 tokens，请检查文本")

        inputs = {key: value.to(args.device) for key, value in inputs.items()}
        with torch.inference_mode():
            scores = model(**inputs).logits.view(-1).float().cpu().tolist()

        if len(scores) != len(passages) or not all(
            torch.isfinite(torch.tensor(score)).item() for score in scores
        ):
            raise RuntimeError("模型返回了无效分数")

        ranked = sorted(
            enumerate(scores), key=lambda item: item[1], reverse=True
        )
        print(f"\n问题：{question}")
        for rank, (index, score) in enumerate(ranked, start=1):
            print(f"{rank}. 原始得分={score:.4f} | {passages[index]}")


if __name__ == "__main__":
    main()