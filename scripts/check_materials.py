"""独立教学fixture检查；默认纯规则，--use-model 才可能调用DeepSeek。"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.knowledge import write_json
from app.workflows.materials import MaterialWorkflow
from app.schemas.materials import WorkflowInput


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--use-model", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = WorkflowInput.model_validate_json(args.fixture.read_text(encoding="utf-8"))
        result = MaterialWorkflow().run(data, args.use_model)
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.output:
            output = args.output.resolve()
            if not output.is_relative_to(ROOT):
                raise ValueError("输出必须位于项目内")
            write_json(output, result)
        return 1 if result["run_status"] == "input_invalid" else 0
    except (OSError, ValueError, KeyError, TypeError):
        print("教学材料输入或Workflow配置无效；未将其判定为检查通过。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
