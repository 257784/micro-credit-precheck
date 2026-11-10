"""为全新空教学库建立当前表结构；不用于升级或迁移已有数据库。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import inspect
from app.db import auth_models  # 注册身份表到同一 metadata
from app.db.models import Base
from app.db.session import get_engine
from app.observability.assistant_audit import events


def initialize(engine):
    inspector = inspect(engine)
    if inspector.get_table_names() or inspector.get_view_names():
        raise RuntimeError('目标数据库已有表或视图；此脚本只允许初始化全新空库。')
    Base.metadata.create_all(engine)
    events.create(engine)


def main():
    engine = get_engine()
    try:
        initialize(engine)
        print('空教学库表结构已创建；没有导入账号或业务数据。')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
