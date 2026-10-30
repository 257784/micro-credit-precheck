"""配置驱动的材料检查：规则决定缺项，模型只提供待确认的类别建议。"""

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.llm.deepseek import GenerationError
from app.workflows.material_names import suggest_names, validate_hints
from app.rules.material_config import expression_codes, load_configuration
from app.schemas.materials import WorkflowInput


class WorkflowInputError(ValueError):
    pass


def blank(value) -> bool:
    return value is None or isinstance(value, str) and not value.strip() or isinstance(value, (list, dict)) and not value


def evaluate_expression(expression: dict, present: set, candidates: set) -> dict:
    """组合判断只认确定性归类；候选走pending，不当作已提交。"""
    op, value = next(iter(expression.items()))
    if op == "leaf":
        if value in present:
            return {"state": "present", "matched": [value], "missing": [], "pending": []}
        if value in candidates:
            return {"state": "pending_classification", "matched": [], "missing": [], "pending": [value]}
        return {"state": "missing", "matched": [], "missing": [value], "pending": []}
    children = [evaluate_expression(child, present, candidates) for child in value]
    rank = {"present": 0, "pending_classification": 1, "missing": 2}
    if op == "any_of":
        best = min(children, key=lambda child: (rank[child["state"]], len(child["missing"]), -len(child["matched"])))
        return {**best, "alternatives": children}
    state = max(children, key=lambda child: rank[child["state"]])["state"]
    return {"state": state, **{key: sorted({code for child in children for code in child[key]})
                              for key in ("matched", "missing", "pending")}}


def expression_text(expression: dict, types: dict) -> str:
    op, value = next(iter(expression.items()))
    if op == "leaf":
        return types[value]["name"]
    joiner = " ＋ " if op == "all_of" else " 或 "
    return "（" + joiner.join(expression_text(child, types) for child in value) + "）"


class MaterialWorkflow:
    def __init__(self, configuration=None, name_suggester=None) -> None:
        self.flow, self.rules, self.nodes = configuration or load_configuration()
        self.name_suggester = name_suggester or suggest_names
        self.aliases = {alias: code for code, item in self.rules["types"].items() for alias in item["aliases"]}

    def run(self, data: WorkflowInput, use_model: bool = False) -> dict:
        """只读运行，结果不保存到旧报告或申请状态。"""
        context = {"input": data, "use_model": use_model, "stop": False, "degraded": False,
                   "active": [], "bindings": {}, "unknown": [], "hints": [], "selected": [],
                   "skipped": [], "checklist": [], "missing_items": [], "abnormal_items": [],
                   "pending_items": [], "warnings": [], "node_trace": []}
        for node in self.nodes:
            started = perf_counter()
            if context["stop"] and node["type"] != "aggregate":
                trace = {"node_id": node["id"], "type": node["type"], "status": "skipped",
                         "branch": "input_stopped", "input_count": 0, "output_count": 0}
            else:
                before = sum(len(context[key]) for key in ("missing_items", "abnormal_items", "pending_items"))
                status, branch = getattr(self, "_" + node["type"])(context)
                after = sum(len(context[key]) for key in ("missing_items", "abnormal_items", "pending_items"))
                trace = {"node_id": node["id"], "type": node["type"], "status": status,
                         "branch": branch, "input_count": len(data.materials), "output_count": after - before}
            trace["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
            context["node_trace"].append(trace)
        issues = context["missing_items"] or context["abnormal_items"] or context["pending_items"]
        status = "input_invalid" if context["stop"] else "dependency_degraded" if context["degraded"] else "completed_with_issues" if issues else "completed"
        return {"run_id": uuid4().hex, "application_id": data.application_id,
                "workflow_id": self.flow["workflow_id"], "workflow_version": self.flow["version"],
                "rules_version": self.rules["version"], "input_mode": data.input_mode,
                "generated_at": datetime.now(timezone.utc).isoformat(), "run_status": status,
                "conditions": data.conditions.model_dump(),
                "material_snapshot": [{"material_id": m.material_id, "version_no": m.version_no,
                                       "material_type": m.material_type, "parse_status": m.parse_status}
                                      for m in context["selected"]],
                "skipped_versions": context["skipped"], "name_hints": context["hints"],
                **{key: context[key] for key in ("checklist", "missing_items", "abnormal_items", "pending_items", "warnings", "node_trace")},
                "suggested_actions": [item["action"] for key in ("missing_items", "abnormal_items", "pending_items")
                                      for item in context[key] if item.get("action")],
                "notice": "按F3虚构教学清单演示；已声明提交不代表内容真实或充分，不改变审批或复核状态。"}

    def _issue(self, context: dict, bucket: str, kind: str, message: str, code=None,
               material=None, field=None, action=None, location=None) -> None:
        item = {"kind": kind, "code": code, "message": message, "material_id": material.material_id if material else None,
                "version_no": material.version_no if material else None, "field": field,
                "evidence_location": location or (material.evidence_location if material else None),
                "action": action or "请人工核对该项及其政策依据。"}
        item["policy_ref"] = self.rules["types"][code]["ref"] if code in self.rules["types"] else None
        context[bucket].append(item)

    def _primary(self, material):
        return material.canonical_code or self.aliases.get(material.material_type.strip())

    def _validate(self, ctx):
        data = ctx["input"]
        ids, versions = set(), set()
        for material in data.materials:
            group = self._primary(material) or material.material_type.strip()
            key = (group, material.version_no)
            if material.application_id != data.application_id or material.material_id in ids or key in versions:
                raise WorkflowInputError("材料跨申请、编号重复或同类型同版本冲突")
            codes = [self._primary(material)] + [section.canonical_code for section in material.sections]
            if any(code and code not in self.rules["types"] for code in codes):
                raise WorkflowInputError("输入引用未知的材料类别")
            if data.input_mode == "legacy_metadata" and material.parse_status == "parsed_mock":
                raise WorkflowInputError("旧材料元数据不能标记为Mock全文解析完成")
            ids.add(material.material_id)
            versions.add(key)
        if data.product not in self.rules["products"]:
            ctx["stop"] = True
            self._issue(ctx, "pending_items", "unknown_product", "申请产品缺失或未知，未猜测必交清单。", action="请确认本申请产品。")
            return "executed", "unknown_product"
        if not data.materials:
            self._issue(ctx, "abnormal_items", "empty_materials", "本申请材料列表为空。", action="请核对申请材料并补交清单要求的资料。")
            return "executed", "empty_materials"
        return "executed", None

    def _snapshot(self, ctx):
        selected = {}
        for material in ctx["input"].materials:
            group = self._primary(material) or material.material_type.strip()
            previous = selected.get(group)
            if previous is None or material.version_no > previous.version_no:
                selected[group] = material
        ctx["selected"] = list(selected.values())
        active_ids = {m.material_id for m in ctx["selected"]}
        ctx["skipped"] = [{"material_id": m.material_id, "version_no": m.version_no,
                            "reason": "同一确定类型存在更高版本，不回退旧版"}
                           for m in ctx["input"].materials if m.material_id not in active_ids]
        ctx["active"] = [r for r in self.rules["rules"] if ctx["input"].product in r["products"]]
        return "executed", None

    def _match(self, ctx):
        for material in ctx["selected"]:
            code = self._primary(material)
            if code:
                ctx["bindings"].setdefault(code, []).append((material, material))
            else:
                ctx["unknown"].append(material)
            for section in material.sections:
                ctx["bindings"].setdefault(section.canonical_code, []).append((material, section))
        return "executed", None

    def _model_hint(self, ctx):
        if not ctx["unknown"]:
            return "skipped", "no_unclassified_materials"
        allowed = set()
        for rule in ctx["active"]:
            allowed.add(rule["code"])
            allowed.update(expression_codes(rule["expression"], set(self.rules["types"])))
        if ctx["use_model"]:
            try:
                hints = self.name_suggester(ctx["unknown"], {c: self.rules["types"][c] for c in allowed})
                # 替身/其他接入同样走结构和证据校验，不给模型开后门。
                import json
                ctx["hints"] = validate_hints(json.dumps({"hints": hints}, ensure_ascii=False), ctx["unknown"], allowed)
            except (GenerationError, OSError, ValueError, KeyError, TypeError, RuntimeError):
                ctx["degraded"] = True
                ctx["warnings"].append("名称辅助节点失败或未配置，已降级为纯规则和人工归类；不表示没有异常。")
        for material in ctx["unknown"]:
            self._issue(ctx, "pending_items", "unclassified_material", "材料名称/类型未确定，不能自动满足必交要求。",
                        material=material, action="人工确认该材料对应的类别；模型候选仅作辅助。")
        return ("degraded", "node_degraded") if ctx["degraded"] else ("executed", None) if ctx["use_model"] else ("skipped", "model_disabled")

    def _readability(self, ctx):
        for material in ctx["selected"]:
            code = self._primary(material)
            if Path(material.file_name).suffix.lower() not in (".pdf", ".docx"):
                self._issue(ctx, "abnormal_items", "unsupported_format", "声明格式非PDF/DOCX；未验证文件真实类型。",
                            code, material, action="请提供教学受理格式的可读取文件。")
            if material.parse_status == "failed":
                self._issue(ctx, "abnormal_items", "unreadable", "材料已声明提交但解析失败，不按未上传处理。",
                            code, material, action="请人工查看或补交可读取版本，不使用旧版冒充新版。")
            elif material.parse_status == "not_available":
                self._issue(ctx, "pending_items", "content_not_checked", "无全文解析结果，教学摘录不代表字段已核验。",
                            code, material, action="提供真实解析结果或人工核验，本轮仅检查声明提交情况。")
        return "executed", "file_issues_recorded" if ctx["abnormal_items"] else None

    def _requirements(self, ctx):
        present = set(ctx["bindings"])
        candidates = {code for hint in ctx["hints"] for code in hint["candidate_codes"]}
        for rule in ctx["active"]:
            code = rule["code"]
            item = {"code": code, "name": self.rules["types"][code]["name"],
                    "policy_ref": self.rules["types"][code]["ref"],
                    "requirement": expression_text(rule["expression"], self.rules["types"]),
                    "condition": rule.get("condition"), "materials": []}
            fact = getattr(ctx["input"].conditions, rule.get("condition", ""), None)
            if rule.get("condition") and (fact is None or fact.value is None):
                item["status"] = "pending_condition"
                label = {"uses_order_contract": "是否以具体订单或合同为用途依据", "is_used_equipment": "设备是否为二手"}[rule["condition"]]
                self._issue(ctx, "pending_items", "pending_condition", "条件未明确，不默认免交或必交。", code,
                            action="请确认：" + label)
            elif rule.get("condition") and fact.value is False:
                item["status"] = "not_applicable"
            else:
                evaluated = evaluate_expression(rule["expression"], present, candidates)
                if evaluated["state"] != "present" and (code in present or code in candidates) and "leaf" not in rule["expression"]:
                    evaluated["state"] = "pending_combination" if code in present else "pending_classification"
                item.update(status=evaluated["state"], combination=evaluated)
                for matched in set(evaluated["matched"]) | ({code} if code in present else set()):
                    for material, _ in ctx["bindings"].get(matched, []):
                        item["materials"].append({"material_id": material.material_id, "version_no": material.version_no,
                                                  "parse_status": material.parse_status})
                if item["status"] == "missing":
                    missing_names = "、".join(self.rules["types"][c]["name"] for c in evaluated["missing"])
                    self._issue(ctx, "missing_items", "missing", "按已确定声明未找到所需材料/组合；可满足任一允许方案。", code,
                                action="核对或补交：" + missing_names + "；完整可选组合：" + item["requirement"])
                elif item["status"] != "present":
                    self._issue(ctx, "pending_items", item["status"], "仅有总类材料或名称候选，尚不能确认组合满足。", code,
                                action="人工核对材料归类及组合：" + item["requirement"])
                if rule.get("manual_sufficiency") and item["status"] == "present":
                    self._issue(ctx, "pending_items", "sufficiency_review", "声明组合已提交，不代表能证明收入或价格事实。", code,
                                action="人工核验组合对应关系、替代条件和证据充分性。")
            ctx["checklist"].append(item)
        return "executed", None

    def _fields(self, ctx):
        active_codes = {r["code"] for r in ctx["active"]}
        for rule in ctx["active"]:
            active_codes.update(expression_codes(rule["expression"], set(self.rules["types"])))
        for code, bindings in ctx["bindings"].items():
            if code not in active_codes:
                continue
            for material, source in bindings:
                if material.parse_status not in ("parsed_mock", "parsed") or Path(material.file_name).suffix.lower() not in (".pdf", ".docx"):
                    continue
                for field in self.rules["types"][code]["fields"]:
                    if field not in source.checked_fields:
                        self._issue(ctx, "pending_items", "field_not_checked", "该字段尚未检查，不能判定已缺失。", code, material, field,
                                    location=f"materials[{material.material_id}].extracted_fields.{field}")
                    elif blank(source.extracted_fields.get(field)):
                        self._issue(ctx, "abnormal_items", "field_missing", "字段检查未找到该必需字段的有效值。", code, material, field,
                                    action="请补充可核对的字段：" + field,
                                    location=f"materials[{material.material_id}].extracted_fields.{field}")
        return "executed", None

    def _aggregate(self, ctx):
        for item in ctx["checklist"]:
            codes = expression_codes(next(r["expression"] for r in ctx["active"] if r["code"] == item["code"]), set(self.rules["types"])) | {item["code"]}
            relevant = [m for code in codes for m, _ in ctx["bindings"].get(code, [])]
            item["readability"] = "unreadable" if any(m.parse_status == "failed" for m in relevant) else "pending" if any(m.parse_status == "not_available" for m in relevant) else "parsed" if relevant and all(m.parse_status == "parsed" for m in relevant) else "mock_parsed" if relevant else "not_available"
            item["field_status"] = "missing_fields" if any(x["code"] in codes and x["kind"] == "field_missing" for x in ctx["abnormal_items"]) else "pending" if any(x["code"] in codes for x in ctx["pending_items"]) else "checked" if relevant and all(m.parse_status == "parsed" for m in relevant) else "checked_mock" if relevant else "not_available"
        return "executed", None
