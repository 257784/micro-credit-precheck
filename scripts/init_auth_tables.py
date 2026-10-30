"""显式创建身份相关表，不修改或清空业务记录。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db.auth_models import ApplicationOwnerRow, LoginSessionRow, UserRow
from app.db.session import get_engine


def main():
    engine = get_engine()
    for table in (UserRow.__table__, LoginSessionRow.__table__, ApplicationOwnerRow.__table__):
        table.create(engine, checkfirst=True)
    print('身份相关表已检查或创建；未改动业务数据。')


if __name__ == '__main__':
    main()
