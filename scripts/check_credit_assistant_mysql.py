"""新建随机 MySQL 测试库，完成助手验证并仅删除本脚本创建的库。"""
import os
from pathlib import Path
import runpy
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    load_dotenv(ROOT / 'backend/.env', override=False)
    url = make_url(os.environ['DATABASE_URL'])
    if url.get_backend_name() != 'mysql':
        raise RuntimeError('MySQL required')
    name = 'credit_test_' + uuid4().hex
    engine = create_engine(url._replace(database=None), isolation_level='AUTOCOMMIT', hide_parameters=True)
    created = False
    try:
        with engine.connect() as connection:
            connection.execute(text('CREATE DATABASE `' + name + '` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci'))
            created = True
        os.environ['CREDIT_ASSISTANT_TEST_URL'] = url.set(database=name).render_as_string(hide_password=False)
        runpy.run_path(str(ROOT / 'scripts/check_credit_assistant_workflows.py'), run_name='__main__')
    finally:
        os.environ.pop('CREDIT_ASSISTANT_TEST_URL', None)
        if created:
            with engine.connect() as connection:
                connection.execute(text('DROP DATABASE `' + name + '`'))
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        original = getattr(exc, 'orig', exc)
        args = getattr(original, 'args', ())
        print('MySQL assistant verification failed:', type(original).__name__, args[0] if args and isinstance(args[0], int) else '')
        raise SystemExit(1)
