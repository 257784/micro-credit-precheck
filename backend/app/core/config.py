"""稳定路径配置；不读取密钥，不改变已有存储位置。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / 'backend'
DATA_ROOT = BACKEND_ROOT / '.data'
WORKFLOW_CONFIG_ROOT = BACKEND_ROOT / 'workflows'
