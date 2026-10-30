"""单次政策问答；凭据由启动进程的环境提供，不打印环境或上游错误正文。"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.policy import QuestionRequest
from app.services.policy import PolicyQA


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--product", choices=["working_capital", "equipment"])
    parser.add_argument("--rerank", action="store_true")
    args = parser.parse_args()
    result = PolicyQA().answer(QuestionRequest(
        question=args.text, product=args.product, rerank=args.rerank,
    ))
    print(result.model_dump_json(indent=2))
    return 1 if result.status.endswith("_error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
