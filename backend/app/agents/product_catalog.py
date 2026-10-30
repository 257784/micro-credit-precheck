"""教学产品目录：只用于识别讨论范围，不判断实际授信资格。"""
from copy import deepcopy

PRODUCT_CATALOG = [
    {'id': 'working_capital', 'name': '经营周转贷（教学产品）',
     'aliases': ['经营周转贷', '经营周转', '周转贷'],
     'scope_refs': [['CC-POL-001', '第一条', '1.0'], ['CC-POL-001', '第二条', '1.0']]},
    {'id': 'equipment', 'name': '设备更新贷（教学产品）',
     'aliases': ['设备更新贷', '设备更新', '设备贷'],
     'scope_refs': [['CC-POL-002', '第一条', '1.0'], ['CC-POL-002', '第二条', '1.0']]},
]


def product_catalog():
    return deepcopy(PRODUCT_CATALOG)
