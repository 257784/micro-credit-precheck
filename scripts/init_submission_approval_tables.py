"""显式创建本轮新增表；不修改已有数据。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db.models import ApprovalRow, MaterialCheckRow
from app.db.session import get_engine

if __name__ == '__main__':
    engine = get_engine()
    MaterialCheckRow.__table__.create(engine, checkfirst=True)
    ApprovalRow.__table__.create(engine, checkfirst=True)
    print('材料检查及审批表已确认存在。')
