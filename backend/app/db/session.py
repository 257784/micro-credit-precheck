"""延迟连接；配置错误安全失败，不静默退回旧存储。"""
import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import make_url

from app.core.config import BACKEND_ROOT
from app.db.models import Base


@lru_cache(maxsize=1)
def get_engine():
    load_dotenv(BACKEND_ROOT / '.env', override=False)
    try:
        url = make_url(os.environ.get('DATABASE_URL', ''))
        testing = os.environ.get('CREDIT_TEST_DATABASE') == '1'
        if url.get_backend_name() != 'mysql' and not (testing and url.get_backend_name() == 'sqlite'):
            raise ValueError()
        engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
        if url.get_backend_name() == 'sqlite':
            @event.listens_for(engine, 'connect')
            def enable_foreign_keys(connection, _):
                connection.execute('PRAGMA foreign_keys=ON')
        return engine
    except Exception:
        raise RuntimeError('数据库配置无效或驱动不可用，请检查 backend/.env。') from None


def verify_database():
    try:
        engine = get_engine()
        with engine.connect() as connection:
            existing = set(inspect(connection).get_table_names())
            if not set(Base.metadata.tables).issubset(existing):
                raise ValueError()
    except Exception:
        raise RuntimeError('数据库不可用或业务表缺失，请检查数据库配置和表结构。') from None
