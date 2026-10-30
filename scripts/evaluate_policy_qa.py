"""Compatibility CLI; implementation is in evals.runners."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.runners.evaluate_policy_qa import *

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # 不输出可能包含认证上下文的第三方 traceback。
        print("问答评测未完成，请检查本机依赖、索引及 DeepSeek 环境设置；没有据此判定通过。", file=sys.stderr)
        raise SystemExit(1)
