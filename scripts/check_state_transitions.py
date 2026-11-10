"""穷举状态转换并验证持久化边界；只使用隔离 SQLite。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from app.db.models import ApplicationRow, ApprovalRow, Base, EnterpriseRow, ReviewRow, StatusRow
from app.repositories.reviews import ReviewConflict
from app.rules.application_states import InvalidTransition, TRANSITIONS, next_status
import app.repositories.sql_business as business


def main():
    states = {'草稿', '待企业补充材料', '待风控复核', '风控复核中', '待审批', '审批中', '审批通过', '审批未通过', '未知状态'}
    for action, transitions in TRANSITIONS.items():
        for state in states:
            if state in transitions:
                assert next_status(state, action) == transitions[state]
            else:
                try:
                    next_status(state, action)
                except InvalidTransition:
                    pass
                else:
                    raise AssertionError((state, action))
    try:
        next_status('审批中', '未知动作')
    except InvalidTransition:
        pass
    else:
        raise AssertionError('未知动作不能流转')

    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    business.get_engine = lambda: engine
    with Session(engine) as session, session.begin():
        session.add(EnterpriseRow(id='e', payload={}))
        session.flush()
        session.add(ApplicationRow(id='a', enterprise_id='e', status='待审批', submitted_at='2026', payload={}))
    store = business.ReviewRepository()
    repo = business.ApplicationRepository()
    # 即使伪造 expected_status 与实际状态相同，也不能从待审批跳到复核完成。
    try:
        store.append('a', '待审批', '待审批', 'complete', 'reviewer')
    except ReviewConflict:
        pass
    else:
        raise AssertionError('仓储允许了非法复核')
    with Session(engine) as session:
        assert session.get(ApplicationRow, 'a').status == '待审批'
        assert session.scalar(select(func.count()).select_from(ReviewRow)) == 0
    assert repo.approval('a', 'approver', 'start') == '审批中'
    assert repo.approval('a', 'approver', 'approve', '已人工确认') == '审批通过'
    for action in ('start', 'approve', 'reject', 'unknown'):
        try:
            repo.approval('a', 'approver', action, '重复')
        except ReviewConflict:
            pass
        else:
            raise AssertionError(('终态不能修改', action))
    with Session(engine) as session:
        assert session.get(ApplicationRow, 'a').status == '审批通过'
        assert session.scalar(select(func.count()).select_from(ApprovalRow)) == 2
        assert session.scalar(select(func.count()).select_from(StatusRow)) == 2
    with Session(engine) as session, session.begin():
        session.get(ApplicationRow, 'a').status = '待风控复核'
    store.append('a', '待风控复核', '待风控复核', 'start', 'reviewer')
    store.append('a', '风控复核中', '风控复核中', 'request_supplement', 'reviewer', review_note='请补充材料')
    with Session(engine) as session:
        assert session.get(ApplicationRow, 'a').status == '待企业补充材料'
        assert session.scalar(select(func.count()).select_from(ReviewRow)) == 2
    engine.dispose()
    print('状态与动作组合、伪造预期状态、终态和风控补件验证通过。')


if __name__ == '__main__':
    main()
