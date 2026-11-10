"""显式创建关键操作日志表，不修改历史数据。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db.models import OperationAuditRow
from app.db.session import get_engine

if __name__ == '__main__':
    OperationAuditRow.__table__.create(get_engine(), checkfirst=True)
    print('关键操作日志表已确认存在。')
