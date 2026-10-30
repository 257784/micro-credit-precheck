"""显式创建助手审计表；仅建表，不修改现有业务表和数据。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db.session import get_engine
from app.observability.assistant_audit import events


def main():
    engine = get_engine()
    try:
        events.create(engine, checkfirst=True)
        print('Assistant audit table is available.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
