"""交互设置全部账号的新密码；不输出、保存或通过参数传递明文密码。"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.authentication import hash_password
from app.db.auth_models import LoginSessionRow, UserRow
from app.db.session import get_engine


def reset_all(engine, replacements):
    """锁定账号并在一个事务中更新哈希、撤销现有会话。"""
    with Session(engine) as session, session.begin():
        users = list(session.scalars(select(UserRow).order_by(UserRow.username).with_for_update()))
        if {user.id for user in users} != set(replacements):
            raise RuntimeError('账号列表已变化，未修改密码，请重新执行。')
        for user in users:
            user.password_hash = replacements[user.id]
        if users:
            session.execute(delete(LoginSessionRow).where(LoginSessionRow.user_id.in_([user.id for user in users])))
    return len(users)


def main():
    engine = get_engine()
    with Session(engine) as session:
        users = list(session.execute(select(UserRow.id, UserRow.username, UserRow.role, UserRow.active).order_by(UserRow.username)))
    if not users:
        print('未找到账号，无需重置。')
        return
    print('将依次为所有账号设置新密码；输入时不会显示字符。按 Ctrl+C 可在提交前取消。')
    replacements = {}
    for user_id, username, role, active in users:
        state = '启用' if active else '停用'
        print(f'账号：{username}（{role}，{state}）')
        while True:
            first = getpass.getpass('新密码（12 至 256 字符）：')
            second = getpass.getpass('再次输入新密码：')
            if first != second:
                print('两次输入不一致，请重新输入。')
                continue
            try:
                replacements[user_id] = hash_password(first)
                break
            except ValueError as error:
                print(str(error))
            finally:
                first = second = None
    count = reset_all(engine, replacements)
    print(f'已重置 {count} 个账号并撤销旧登录会话。账号 ID、角色、启停状态与申请归属未改变。')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n已取消；若尚未完成事务，数据库中的密码没有改变。')
        raise SystemExit(1) from None
