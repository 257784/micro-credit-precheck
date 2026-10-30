"""依据CC-MAT-001及任务卡重建的教学规则；不是原丢失配置的逐字还原。"""
from copy import deepcopy

from app.rag.knowledge import PRODUCTS

COMMON = ['working_capital', 'equipment']


def material(name, clause, fields, aliases=()):
    return {'name': name, 'ref': ['CC-MAT-001', '1.0', clause],
            'fields': fields, 'aliases': [name, *aliases]}


TYPES = {
    'M-C01': material('授信申请表', '第二条', ['主体名称', '统一社会信用代码', '申请产品', '申请金额', '金额单位', '用途', '联系人', '提交日期', '真实性确认']),
    'M-C02': material('主体登记资料', '第二条', ['主体名称', '统一社会信用代码', '主体类型'], ['营业执照']),
    'M-C03': material('经营情况说明', '第二条', ['主要业务', '经营场所', '主要交易情况', '融资需求']),
    'M-W01': material('经营收入佐证', '第三条', []),
    'M-W02': material('资金用途说明', '第三条', ['用途', '预计使用时间', '采购或支出背景', '支付对象或尚未确定原因']),
    'M-W03': material('对应交易背景资料', '第三条', []),
    'M-E01': material('设备采购计划', '第四条', ['设备名称', '规格', '数量', '单价', '总价', '供应商', '采购时间', '安装安排', '费用构成']),
    'M-E02': material('采购价格依据', '第四条', []),
    'M-E03': material('二手设备使用及来源说明', '第四条', ['已知年限', '现状', '转让方', '权属或来源资料']),
    'D-ACCOUNT': material('经营账户收款记录', '第三条', []),
    'D-CLASSIFY': material('收入分类说明', '第三条', []),
    'D-LEDGER': material('销售台账', '第三条', []),
    'D-ORDER': material('订单或发票', '第三条', []),
    'D-RELATION': material('对应关系说明', '第三条', []),
    'D-CONTRACT': material('设备采购合同', '第四条', ['供应商', '规格', '数量', '价格', '日期']),
    'D-QUOTE': material('供应商报价单', '第四条', ['供应商', '规格', '数量', '价格', '日期']),
    'D-UNSIGNED': material('未签约说明', '第四条', ['未签约原因', '后续安排']),
}


def leaf(code):
    return {'leaf': code}


def rule(code, products, expression=None, condition=None, manual_sufficiency=False):
    result = {'code': code, 'products': products, 'expression': expression or leaf(code),
              'manual_sufficiency': manual_sufficiency}
    if condition:
        result['condition'] = condition
    return result


MATERIAL_RULES = {'version': '1.0-reconstructed', 'products': PRODUCTS, 'types': TYPES, 'rules': [
    *[rule(code, COMMON) for code in ('M-C01', 'M-C02', 'M-C03')],
    rule('M-W01', ['working_capital'], {'any_of': [
        {'all_of': [leaf('D-ACCOUNT'), leaf('D-CLASSIFY')]},
        {'all_of': [leaf('D-LEDGER'), leaf('D-ORDER'), leaf('D-RELATION')]}]}, manual_sufficiency=True),
    rule('M-W02', ['working_capital']),
    rule('M-W03', ['working_capital'], condition='uses_order_contract'),
    rule('M-E01', ['equipment']),
    rule('M-E02', ['equipment'], {'any_of': [leaf('D-CONTRACT'),
        {'all_of': [leaf('D-QUOTE'), leaf('D-UNSIGNED')]}]}, manual_sufficiency=True),
    rule('M-E03', ['equipment'], condition='is_used_equipment'),
]}

MATERIAL_NODES = ('validate', 'snapshot', 'match', 'model_hint', 'readability', 'requirements', 'fields', 'aggregate')
MATERIAL_FLOW = {'workflow_id': 'material-completeness', 'version': '1.0-reconstructed',
    'nodes': [{'id': node, 'type': node, 'next': [MATERIAL_NODES[i + 1]] if i + 1 < len(MATERIAL_NODES) else [],
               'branches': []} for i, node in enumerate(MATERIAL_NODES)]}

RISK_NODES = ['snapshot', 'materials', 'policy', 'deterministic', 'model', 'validate', 'aggregate']
RISK_FLOW = {'version': '1.0', 'nodes': RISK_NODES, 'routes': {
    'snapshot': {'continue': 'materials'}, 'materials': {'continue': 'policy'},
    'policy': {'continue': 'deterministic', 'unknown_product': 'deterministic'},
    'deterministic': {'fixture_checked': 'model', 'facts_unavailable': 'model'},
    'model': {state: 'validate' for state in ('disabled', 'skipped_no_materials', 'skipped_unknown_product',
        'skipped_retrieval_failed', 'skipped_no_readable_evidence', 'completed', 'failed')},
    'validate': {'continue': 'aggregate'}, 'aggregate': {'continue': None},
}}
RISK_RULES = {'version': '1.0', 'rules': [
    {'id': 'subject', 'products': COMMON, 'check': 'subject_name', 'ref': ['CC-REV-001', '1.0', '第二条']},
    {'id': 'equipment-amount', 'products': ['equipment'], 'check': 'amount_comparison', 'ref': ['CC-POL-002', '1.0', '第六条']},
    {'id': 'working-amount', 'products': ['working_capital'], 'check': 'amount_comparison', 'ref': ['CC-POL-001', '1.0', '第五条']},
    {'id': 'income', 'products': ['working_capital'], 'check': 'income_period', 'ref': ['CC-POL-001', '1.0', '第五条']},
]}


def definitions():
    return deepcopy((MATERIAL_FLOW, MATERIAL_RULES, RISK_FLOW, RISK_RULES))
