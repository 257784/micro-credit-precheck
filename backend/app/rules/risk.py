"""有限的教学事实核对；fixture 数据不能作为正式申请事实。"""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


def evaluate_fixture(facts):
    """仅对明确来源和口径的虚构事实计算，不推断缺失值。"""
    if facts.get("source") != "fixture":
        raise ValueError("结构化事实仅允许 fixture 来源")
    product = facts.get("product")
    if product not in ("working_capital", "equipment"):
        raise ValueError("未知产品，不执行产品规则")
    findings, missing = [], []
    names = facts.get("names", {})
    if names.get("application") and names.get("registration"):
        if names["application"].strip() != names["registration"].strip():
            findings.append({"rule_id": "subject-name", "category": "subject_review",
                             "description": "主体名称不同，需核实简称、历史名称或变更关系；不认定欺诈。",
                             "evidence": [{"location": "names.application", "quote": names["application"]},
                                          {"location": "names.registration", "quote": names["registration"]}],
                             "policy_ref": ["CC-REV-001", "1.0", "第二条"]})
    else:
        missing.append("主体名称或登记名称未提供，无法比较。")
    amounts = facts.get("amounts", {})
    left, right = amounts.get("application", {}), amounts.get("material", {})
    fields = ("value", "currency", "unit", "period", "tax_basis")
    if not all(left.get(k) is not None and right.get(k) is not None and str(left[k]).strip() and str(right[k]).strip() for k in fields):
        missing.append("金额或币种、单位、期间、含税口径未完整提供，未计算差异。")
    elif any(left[k] != right[k] for k in fields[1:]):
        missing.append("金额口径不一致，需人工核实后再比较。")
    else:
        try:
            a, b = Decimal(str(left["value"])), Decimal(str(right["value"]))
            if not a.is_finite() or not b.is_finite():
                raise InvalidOperation
            if a != b:
                findings.append({"rule_id": "amount-comparison", "category": "amount_review",
                                 "description": f"同口径金额存在差异：{a} 与 {b}，请人工核实原因。",
                                 "evidence": [{"location": "amounts.application", "quote": str(a)},
                                              {"location": "amounts.material", "quote": str(b)}],
                                 "policy_ref": ["CC-POL-001", "1.0", "第七条"] if product == "working_capital" else ["CC-POL-002", "1.0", "第六条"]})
        except (InvalidOperation, ValueError):
            missing.append("金额无法识别，未计算差异。")
    submitted = facts.get("submitted_date")
    period = None
    if submitted and product == "working_capital":
        current = date.fromisoformat(submitted).replace(day=1)
        end = current - timedelta(days=1)
        month_index = current.year * 12 + current.month - 1 - 3
        start = date(month_index // 12, month_index % 12 + 1, 1)
        period = {"start": start.isoformat(), "end": end.isoformat(), "basis": "申请提交日期前三个完整自然月"}
        if facts.get("operating_under_three_months") is True and not facts.get("operating_start_date"):
            missing.append("经营不足三个月，开始经营日期未知，期间需人工确认。")
            period = None
        elif facts.get("operating_under_three_months") is True:
            start = date.fromisoformat(facts["operating_start_date"])
            end = date.fromisoformat(submitted) - timedelta(days=1)
            if start > end:
                raise ValueError("开始经营日期晚于核验截止日期")
            period = {"start": start.isoformat(), "end": end.isoformat(), "basis": "经营不足三个月的实际期间，需核对说明"}
    elif product == "working_capital":
        missing.append("申请提交日期缺失，无法计算收入期间。")
    return {"findings": findings, "missing_info": missing, "income_period": period, "source": "fixture"}
