"""隔离验证条件复用、材料候选、冲突与对话澄清。"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.agents.condition_dialogue import explicit_conditions, interpret_condition, pending_from_results
from app.schemas.business import Application, ApplicationDetail, Enterprise
from app.schemas.materials import Conditions, Fact
from app.services.condition_facts import resolve_conditions


def document(identifier, version, value, status='parsed', application='APP-1'):
    return {'id': identifier, 'version': version, 'application_id': application, 'category': 'M-E01',
            'parsed': {'status': status, 'fields': {'设备新旧': {'value': value, 'location': '段落3'}},
                       'sections': [{'location': '段落3', 'text': '设备新旧：' + value}]}}


def main():
    application = Application(application_id='APP-1', enterprise_id='E', product_type='设备更新贷（教学产品）',
        requested_amount=1, status='待风控复核', account_manager_id='M', account_manager_name='教学', submitted_at='2026',
        condition_facts={'is_used_equipment': {'value': False, 'source': 'application_field', 'location': '企业申请声明'}})
    enterprise = Enterprise(enterprise_id='E', enterprise_name='教学', industry='教学', registered_region='教学', created_at='2026')
    detail = ApplicationDetail(application=application, enterprise=enterprise, materials=[], reports=[], status_history=[])
    with patch('app.services.documents.DocumentService.list', return_value=[]):
        facts, candidates, conflicts = resolve_conditions(detail, Conditions())
        assert facts.is_used_equipment.value is False and facts.is_used_equipment.source == 'application_field'
        assert not candidates and not conflicts
        facts, _, conflicts = resolve_conditions(detail, Conditions(is_used_equipment=Fact(value=True, source='manual_demo', location='测试')))
        assert facts.is_used_equipment is None and conflicts == ['is_used_equipment']
    with patch('app.services.documents.DocumentService.list', return_value=[document('old', 1, '二手'), document('new', 2, '全新')]):
        facts, candidates, conflicts = resolve_conditions(detail, Conditions())
        assert facts.is_used_equipment.value is False and not conflicts
        assert len(candidates) == 1 and candidates[0]['material_id'] == 'new' and candidates[0]['location'] == '段落3'
    with patch('app.services.documents.DocumentService.list', return_value=[document('new', 2, '二手')]):
        facts, candidates, conflicts = resolve_conditions(detail, Conditions())
        assert facts.is_used_equipment is None and conflicts == ['is_used_equipment'] and candidates[0]['quote'] == '设备新旧：二手'
    detail.application.condition_facts = {}
    with patch('app.services.documents.DocumentService.list', return_value=[document('new', 2, '二手')]):
        facts, candidates, _ = resolve_conditions(detail, Conditions())
        assert facts.is_used_equipment is None and len(candidates) == 1
    with patch('app.services.documents.DocumentService.list', return_value=[document('new', 2, '二手', status='failed')]):
        assert not resolve_conditions(detail, Conditions())[1]
    assert interpret_condition('是二手设备', 'is_used_equipment') is True
    assert interpret_condition('不是', 'is_used_equipment') is False
    assert interpret_condition('可能是二手', 'is_used_equipment') is None
    assert interpret_condition('是新的', 'is_used_equipment') is False
    assert interpret_condition('有合同', 'uses_order_contract') is None
    assert interpret_condition('是', None) is None
    assert explicit_conditions('这次购买二手设备，请检查材料')['is_used_equipment'] is True
    assert not explicit_conditions('是否购买二手设备？')
    assert not explicit_conditions('我不购买二手设备')
    assert explicit_conditions('没有以具体合同作为用途依据')['uses_order_contract'] is False
    flow = {'pending_items': [{'action': '请确认：设备是否为二手'}]}
    assert pending_from_results([('check_materials', {'status': 'ok', 'workflow': flow})]) == ('is_used_equipment', 'check_materials')
    print('条件声明复用、材料候选、冲突及对话澄清隔离验证通过。')


if __name__ == '__main__':
    main()
