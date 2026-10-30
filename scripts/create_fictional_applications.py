"""显式创建十笔虚构教学申请和真实DOCX正文；不覆盖已有申请。"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'scripts'))

from sqlalchemy.orm import Session
from app.db.models import ApplicationRow, EnterpriseRow
from app.db.session import get_engine
from app.repositories.sql_documents import SQLDocumentStore
from app.schemas.business import Application, Enterprise
from build_document_cases import CASES, NAME, write_docx

OUT = ROOT / 'fixtures' / 'fictional_applications'
SCENARIOS = [
    ('normal_1', '正常完整材料'), ('normal_2', '正常完整材料'),
    ('missing_quote', '缺少报价单'), ('missing_registration', '缺少主体登记材料'),
    ('amount_difference', '报价与计划金额不一致'), ('name_difference', '申请与登记主体名称不一致'),
    ('missing_price', '报价缺少价格字段'), ('missing_tax', '报价缺少含税口径'),
    ('invalid_quote', '报价文件无法解析'), ('missing_plan', '缺少设备采购计划'),
]


def main():
    engine = get_engine()
    ids = [f'APP-FICT-{i:03}' for i in range(1, 11)]
    try:
        with Session(engine) as session:
            if any(session.get(ApplicationRow, item) or session.get(EnterpriseRow, item.replace('APP-', 'ENT-')) for item in ids):
                raise RuntimeError('目标申请或企业ID已存在；拒绝覆盖，请人工核对。')
        if OUT.exists():
            raise RuntimeError('样例目录已存在；拒绝覆盖，请人工核对。')
        OUT.mkdir(parents=True)
        manifest = []
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        for index, (scenario, description) in enumerate(SCENARIOS, 1):
            application_id = ids[index - 1]
            enterprise_id = application_id.replace('APP-', 'ENT-')
            name = f'澄川教学示例{index:02}号包装科技有限公司（虚构）'
            files = []
            for code, (title, source) in CASES.items():
                if (scenario == 'missing_quote' and code == 'D-QUOTE') or (scenario == 'missing_registration' and code == 'M-C02') or (scenario == 'missing_plan' and code == 'M-E01'):
                    continue
                fields = {key: value.replace(NAME, name).replace('DEMO-QH-001', f'DEMO-FICT-{index:03}') for key, value in source.items()}
                if scenario == 'amount_difference' and code == 'D-QUOTE':
                    fields.update(价格='150000', 单价='75000')
                if scenario == 'name_difference' and code == 'M-C02':
                    fields['主体名称'] = '澄川另一家教学企业（虚构）'
                if scenario == 'missing_price' and code == 'D-QUOTE':
                    fields.pop('价格')
                if scenario == 'missing_tax' and code == 'D-QUOTE':
                    fields.pop('含税口径')
                path = OUT / application_id / (code + '-' + title + '.docx')
                if scenario == 'invalid_quote' and code == 'D-QUOTE':
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('虚构教学异常：此文件为错误格式，无法解析为DOCX。', encoding='utf-8')
                else:
                    write_docx(path, title, fields)
                files.append({'category': code, 'file': str(path.relative_to(ROOT))})
            enterprise = Enterprise(enterprise_id=enterprise_id, enterprise_name=name, industry='包装加工（虚构）',
                registered_region='澄川教学园区（虚构）', created_at=now)
            application = Application(application_id=application_id, enterprise_id=enterprise_id,
                product_type='设备更新贷（教学产品）', requested_amount=120000, status='待风控复核',
                account_manager_id='MANAGER-TEACHING', account_manager_name='教学客户经理', submitted_at=now)
            manifest.append(dict(application_id=application_id, enterprise=enterprise.model_dump(),
                application=application.model_dump(), scenario=scenario, description=description, files=files))
        (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        with Session(engine) as session, session.begin():
            for item in manifest:
                e, a = item['enterprise'], item['application']
                session.add(EnterpriseRow(id=e['enterprise_id'], payload=e))
                session.flush()
                session.add(ApplicationRow(id=a['application_id'], enterprise_id=e['enterprise_id'],
                    status=a['status'], submitted_at=a['submitted_at'], payload=a))
            session.flush()
        store = SQLDocumentStore()
        for item in manifest:
            for file in item['files']:
                path = ROOT / file['file']
                result = store.upload(item['application_id'], file['category'], path.name, path.read_bytes())
                print(item['application_id'], file['category'], result['parsed']['status'])
        print('Created:', len(manifest), 'applications; manifest:', OUT / 'manifest.json')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
