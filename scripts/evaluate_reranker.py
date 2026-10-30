"""Compatibility CLI; implementation is in evals.runners."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.runners.evaluate_reranker import *

if __name__ == "__main__":
    raise SystemExit(main())
