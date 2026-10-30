"""从虚构 fixture 验证统一流程；仅 --use-model 调用外部服务。"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.workflows.risk import run_risk_precheck
from app.schemas.materials import CheckRequest
from app.repositories.sql_business import ApplicationRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--output")
    parser.add_argument("--use-model", action="store_true", help="显式调用DeepSeek，可能产生费用")
    args = parser.parse_args()
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    repository = ApplicationRepository()
    detail = repository.get_application("APP-DEMO-003")
    if fixture.get("empty_materials"):
        detail = detail.model_copy(update={"materials": []})
    result = run_risk_precheck(detail, CheckRequest(use_model=args.use_model), fixture_facts=fixture)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        target = Path(args.output).resolve()
        if not target.is_relative_to(ROOT):
            parser.error("输出须位于项目目录")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
