"""交互创建教学账号；凭据不会进入命令行参数、输出或仓库。"""
import getpass
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.authentication import hash_password
from app.db.auth_models import UserRow
from app.db.session import get_engine


def main():
    username = input('账号：').strip()
    display_name = input('显示名称：').strip()
    role = input('角色（enterprise / customer_manager / risk_reviewer）：').strip()
    if not username or len(username) > 100 or not display_name or len(display_name) > 100 or role not in ('enterprise', 'customer_manager', 'risk_reviewer'):
        raise ValueError('账号、显示名称或角色无效')
    secret_value = getpass.getpass('登录凭据（至少 12 字符）：')
    if secret_value != getpass.getpass('确认登录凭据：'):
        raise ValueError('两次输入不一致')
    fields = {'id': uuid4().hex, 'username': username, 'display_name': display_name,
              'role': role, 'password_hash': hash_password(secret_value), 'active': True}
    with Session(get_engine()) as session, session.begin():
        if session.scalar(select(UserRow.id).where(UserRow.username == username)):
            raise ValueError('账号已存在')
        session.add(UserRow(**fields))
    print('账号已创建。')


if __name__ == '__main__':
    main()
