import sys
"""显式调用已启动后端的真实模型；不读取或记录任何凭据。"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from time import perf_counter
import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', help='确认调用真实服务，可能产生费用')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--case', choices=['NORMAL','CONTENT','AMOUNT'], action='append')
    args = parser.parse_args()
    if not args.run:
        parser.error('须显式提供 --run 才调用真实服务')
    manifest = json.loads((ROOT/'mock_data/document_cases/manifest.json').read_text(encoding='utf-8'))
    output = ROOT/'docs/f3-knowledge-base/management/workflow-evidence/document-model-live.json'
    report = {'started_at':datetime.now(timezone.utc).isoformat(), 'mode':'real_backend_no_mock', 'cases':{}}
    if args.case and output.exists():
        report = json.loads(output.read_text(encoding='utf-8'))
    with httpx.Client(base_url=args.base_url, timeout=300) as client:
        for case in args.case or ['NORMAL','CONTENT','AMOUNT']:
            path = '/api/applications/APP-DOC-'+case
            for entry in manifest:
                relative = entry['file']
                if entry['category']=='D-QUOTE' and case!='NORMAL':
                    relative = {'CONTENT':'invalid_content/供应商报价单.docx','AMOUNT':'amount_difference/供应商报价单.docx'}[case]
                file = ROOT/'mock_data/document_cases'/relative
                response = client.post(path+'/documents',params={'category':entry['category'],'filename':file.name},content=file.read_bytes())
                response.raise_for_status()
            options = {'conditions':{'is_used_equipment':{'value':False,'source':'manual_demo','location':'采购计划明确全新设备'}}}
            material = client.post(path+'/materials/check',json=options)
            material.raise_for_status()
            print(case+' requesting real model',flush=True)
            start = perf_counter()
            response = client.post(path+'/risk-precheck',json={**options,'use_model':True})
            response.raise_for_status()
            result = response.json()
            report['cases'][case] = {'elapsed_seconds':round(perf_counter()-start,2),'material':material.json(),'risk':result}
            output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(case, 'retrieval='+result['retrieval_status'], 'model='+result['model_status'], 'run='+result['run_status'],flush=True)
    print('Evidence: '+str(output),flush=True)


if __name__=='__main__':
    main()
