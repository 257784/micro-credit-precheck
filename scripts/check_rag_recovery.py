"""核验Python配置、历史快照及问答接线；--live会运行真实向量检索。"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT))

from app.agents.policy_scope import catalog_and_chunks
from app.rag.knowledge import load_chunks, load_config
from app.rag.vector_store import model_fingerprint
from app.schemas.policy import QuestionRequest
from app.services.policy import PolicyQA
from app.agents.context import RequestContext
from app.tools.assistant_tools import ToolExecutor
from app.observability.assistant_audit import AuditStore, events
from evals.runners.evaluate_retrieval import validate_cases, retrieve
from sqlalchemy import create_engine

CASES = ('Q01', 'Q02', 'Q05', 'Q06', 'Q14')
OUT = ROOT / 'docs/architecture/25-rag-restoration-evidence.json'


def check_snapshot(config, signature):
    state = json.loads((ROOT / config['output_dir'] / 'active-index.json').read_text(encoding='utf-8'))
    result = {'corpus_signature_matches': state['corpus_signature'] == signature,
              'model_fingerprint_matches': state['model_fingerprint'] == model_fingerprint(ROOT / config['model_dir'])}
    path = (ROOT / config['chroma_dir'] / 'chroma.sqlite3').resolve()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        row = connection.execute('SELECT id,dimension FROM collections WHERE name=?', (state['collection'],)).fetchone()
        result['collection_exists'] = bool(row)
        if row:
            metadata = {r[0]: next((v for v in r[1:] if v is not None), None) for r in connection.execute(
                'SELECT key,str_value,int_value,float_value,bool_value FROM collection_metadata WHERE collection_id=?', (row[0],))}
            result['dimension_matches'] = row[1] == state['dimension']
            result['collection_complete'] = bool(metadata.get('complete'))
            result['collection_signature_matches'] = metadata.get('signature') == state['signature']
            count = connection.execute('SELECT count(*) FROM embeddings WHERE segment_id IN (SELECT id FROM segments WHERE collection=?)', (row[0],)).fetchone()[0]
            result['record_count'] = count
            result['record_count_matches'] = count == state['count']
    return result


def summarize(cases, rankings):
    output = []
    for case in cases:
        rows = rankings[case['id']][:8]
        candidates = [{'document_id': x['metadata']['document_id'], 'clause': x['metadata']['clause'],
                       'version': x['metadata']['version'], 'distance': x['cosine_distance']} for x in rows]
        found = {(x['document_id'], x['clause'], x['version']) for x in candidates}
        expected = [tuple(x) for x in case['relevant']]
        output.append({'id': case['id'], 'question': case['question'], 'product': case['product'],
            'expected': case['relevant'], 'missing': [list(x) for x in expected if x not in found],
            'candidate_count': len(candidates), 'candidates': candidates,
            'note': '无标注依据：候选不等于可回答，需在生成层验证拒答' if not expected else '仅评估标注依据覆盖'})
    return output


def check_mock_wiring(historical):
    rows = historical['rankings']['Q06'][:8]
    quote = rows[0]['text'].split('\n\n', 1)[-1][:30]
    class Model:
        settings = SimpleNamespace(model='mock')
        def complete(self, messages):
            return json.dumps({'status': 'answered', 'statements': [{'text': '请核对政策原文及条件。',
                'evidence': [{'source_id': 'S1', 'quote': quote}]}], 'missing_information': []}, ensure_ascii=False)
    qa = PolicyQA(retriever=lambda question, product: rows, client_factory=Model)
    response = qa.answer(QuestionRequest(question='设备更新贷资料如何核对？', product='equipment'))
    assert response.status == 'answered' and response.cited_source_ids == ['S1']
    engine = create_engine('sqlite:///:memory:')
    try:
        events.create(engine)
        context = RequestContext('test', 'customer_manager', frozenset(), 'conv', 'request', 'run')
        executor = ToolExecutor(None, AuditStore(engine))
        with patch('app.services.policy.retrieve_candidates', return_value=rows):
            result = executor.execute(context, 'search_policy', '{"question":"设备","product":"equipment"}', 'call')
        assert result['status'] == 'ok' and result['sources'][0]['document_id'] == rows[0]['metadata']['document_id']
    finally:
        engine.dispose()
    return {'policy_answer': 'passed_with_mock_model_and_historical_candidates',
            'assistant_tool': 'passed_with_historical_candidates'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='加载本地模型并查询实际Chroma')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    args = parser.parse_args()
    config = load_config()
    chunks, signature = load_chunks(config)
    products, _, _, _ = catalog_and_chunks()
    dataset = json.loads((ROOT / 'docs/f3-knowledge-base/management/retrieval-cases.json').read_text(encoding='utf-8'))
    cases = [x for x in validate_cases(dataset, chunks) if x['id'] in CASES]
    if len(cases) != 5:
        raise ValueError('五个验证问题不完整')
    historical = json.loads((ROOT / config['output_dir'] / 'top-k-evaluation/report.json').read_text(encoding='utf-8'))
    if historical['corpus_signature'] != signature:
        raise ValueError('历史评测与当前语料签名不同，不可作为相同语料证据')
    result = {'config_source': 'app.rag.settings', 'chunk_count': len(chunks),
        'product_count': len(products), 'snapshot_metadata': check_snapshot(config, signature),
        'historical_run_at': historical['run_at'], 'historical_method': historical['method'],
        'historical_cases': summarize(cases, historical['rankings']), 'mock_wiring': check_mock_wiring(historical),
        'live': {'status': 'not_run'}}
    if args.live:
        try:
            rankings, _ = retrieve(config, signature, cases, args.device, retrieval_k=8)
            result['live'] = {'status': 'completed', 'device': args.device, 'cases': summarize(cases, rankings)}
        except Exception as error:
            result['live'] = {'status': 'failed', 'error_type': type(error).__name__,
                              'message': '本地模型或Chroma不可用，未完成真实检索。'}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('snapshot metadata:', result['snapshot_metadata'])
    print('historical:', result['historical_run_at'], '; cases:', len(result['historical_cases']))
    print('mock wiring:', result['mock_wiring'])
    print('live:', result['live']['status'])
    return 1 if args.live and result['live']['status'] != 'completed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
