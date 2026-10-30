"""Compatibility CLI; implementation is in evals.runners."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.runners.evaluate_policy_conversation import *

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("多轮验收未完成，请检查本机后端和环境；已有JSON可能只有部分轮次，不判定通过。", file=sys.stderr)
        raise SystemExit(1)
