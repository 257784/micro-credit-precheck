"""验证受控Workflow与材料规则，配置不包含可执行代码。"""

import json
from pathlib import Path

from app.rag.knowledge import PRODUCTS, ROOT, CLAUSE
from app.rules.workflow_definitions import definitions

NODE_TYPES = ("validate", "snapshot", "match", "model_hint", "readability", "requirements", "fields", "aggregate")
CONDITIONS = {"uses_order_contract", "is_used_equipment"}
BRANCHES = {"input_invalid", "empty_materials", "unknown_product", "model_disabled", "node_degraded",
            "unreadable", "unsupported_format", "content_not_checked", "pending_condition", "missing",
            "pending_classification", "pending_combination", "field_missing", "field_not_checked"}


def expression_codes(expression: dict, known: set, depth: int = 0) -> set:
    if not isinstance(expression, dict) or len(expression) != 1 or depth > 8:
        raise ValueError("非法或过深的组合规则")
    op, value = next(iter(expression.items()))
    if op == "leaf":
        if not isinstance(value, str) or value not in known:
            raise ValueError("组合规则引用未知材料")
        return {value}
    if op not in ("all_of", "any_of") or not isinstance(value, list) or not 1 <= len(value) <= 12:
        raise ValueError("未知组合操作符或空组合")
    result = set()
    for child in value:
        result.update(expression_codes(child, known, depth + 1))
    return result


def validate_configuration(flow: dict, rules: dict, references: set) -> list:
    if not flow.get("workflow_id") or not flow.get("version") or not rules.get("version"):
        raise ValueError("缺少流程或规则版本")
    if rules.get("products") != PRODUCTS:
        raise ValueError("规则产品与知识库产品不一致")
    nodes = flow["nodes"]
    mapping = {node["id"]: node for node in nodes}
    if len(mapping) != len(nodes) or len(nodes) != len(NODE_TYPES):
        raise ValueError("节点重复或缺失")
    ordered, visiting, visited = [], set(), set()

    def visit(node_id):
        if node_id in visiting or node_id not in mapping:
            raise ValueError("流程有环或引用未知节点")
        if node_id in visited:
            return
        node = mapping[node_id]
        if node["type"] not in NODE_TYPES or len(node["next"]) > 1:
            raise ValueError("未知节点或非线性主链")
        if not isinstance(node.get("branches", []), list) or set(node.get("branches", [])) - BRANCHES:
            raise ValueError("未知异常分支")
        visiting.add(node_id)
        ordered.append(node)
        for target in node["next"]:
            visit(target)
        visiting.remove(node_id)
        visited.add(node_id)

    visit(nodes[0]["id"])
    if len(visited) != len(nodes) or tuple(n["type"] for n in ordered) != NODE_TYPES:
        raise ValueError("终点不可达或节点依赖顺序错误")
    types = rules["types"]
    aliases = set()
    for code, item in types.items():
        if tuple(item["ref"]) not in references or not item["name"]:
            raise ValueError("规则缺少有效政策出处")
        if len(set(item["fields"])) != len(item["fields"]):
            raise ValueError("字段定义重复")
        for alias in item["aliases"]:
            if not alias.strip() or alias in aliases:
                raise ValueError("材料类型别名重复或为空")
            aliases.add(alias)
    seen = set()
    for rule in rules["rules"]:
        if rule["code"] not in types or rule["code"] in seen:
            raise ValueError("规则编号未知或重复")
        seen.add(rule["code"])
        if not rule["products"] or set(rule["products"]) - set(rules["products"]):
            raise ValueError("规则产品范围无效")
        if rule.get("condition") and rule["condition"] not in CONDITIONS:
            raise ValueError("条件表达式无效")
        expression_codes(rule["expression"], set(types))
    return ordered


def policy_references():
    """核对规则引用的文号、版本和条号，不依赖向量索引配置。"""
    folder = ROOT / 'docs/f3-knowledge-base'
    manifest = json.loads((folder / 'corpus-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('fictional') is not True or manifest.get('status') != 'teaching_draft':
        raise ValueError('仅接受虚构教学语料')
    refs = set()
    for document in manifest['documents']:
        path = (folder / document['path']).resolve()
        if not path.is_relative_to((folder / 'corpus').resolve()):
            raise ValueError('政策文件越出语料目录')
        content = path.read_text(encoding='utf-8')
        if f"| 文号 | {document['document_id']} |" not in content or f"| 版本 | {document['version']} |" not in content:
            raise ValueError('政策正文与清单不一致')
        matches = list(CLAUSE.finditer(content))
        if len(matches) != document['clause_count']:
            raise ValueError('政策条款数量不一致')
        refs.update((document['document_id'], document['version'], match.group(1)) for match in matches)
    return refs


def load_configuration() -> tuple[dict, dict, list]:
    flow, rules, _, _ = definitions()
    refs = policy_references()
    return flow, rules, validate_configuration(flow, rules, refs)
