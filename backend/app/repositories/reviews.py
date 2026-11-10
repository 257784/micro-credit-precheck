"""Shared review states/errors and legacy migration source location; no storage connection."""
from app.core.config import DATA_ROOT
from app.rules.application_states import TRANSITIONS
DEFAULT_DB_PATH = DATA_ROOT / "reviews.sqlite3"
STATUS_BY_ACTION = {
    "start": TRANSITIONS['review_start']['待风控复核'],
    "complete": TRANSITIONS['review_complete']['风控复核中'],
    "request_supplement": TRANSITIONS['request_supplement']['风控复核中'],
}


class ReviewConflict(Exception):
    """申请状态已变化，当前操作不可重复。"""


class ReviewInputError(Exception):
    """复核内容与当前报告不匹配。"""
