"""本地教学知识库默认配置；凭据仍由环境变量管理。"""
from copy import deepcopy

KNOWLEDGE_SETTINGS = {
    'manifest': 'docs/f3-knowledge-base/corpus-manifest.json',
    'model_dir': 'models/bge-m3',
    'chroma_dir': 'backend/.data/chroma',
    'output_dir': 'backend/.data/knowledge-base',
    'model_id': 'BAAI/bge-m3',
    'dimension': 1024,
    'max_tokens': 2048,
    'batch_size': 1,
    'collection_prefix': 'cc_policy',
    'section_product_scopes': {'CC-MAT-001': {
        '第三条': ['working_capital'], '第四条': ['equipment'],
    }},
}


def knowledge_settings():
    return deepcopy(KNOWLEDGE_SETTINGS)
