"""Shared review states/errors and legacy migration source location; no storage connection."""
from app.core.config import DATA_ROOT
DEFAULT_DB_PATH = DATA_ROOT / "reviews.sqlite3"
STATUS_BY_ACTION = {
    "start": "风控复核中",
    "complete": "待审批",
    "request_supplement": "待企业补充材料",
}


class ReviewConflict(Exception):
    """申请状态已变化，当前操作不可重复。"""


class ReviewInputError(Exception):
    """复核内容与当前报告不匹配。"""
