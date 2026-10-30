"""只记录工具调用元数据；审计写入失败时不执行工具。"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, insert, select, update

from app.db.session import get_engine

metadata = MetaData()
events = Table('assistant_tool_audit', metadata,
    Column('event_id', String(32), primary_key=True),
    Column('occurred_at', DateTime(timezone=True), nullable=False, index=True),
    Column('run_id', String(32), nullable=False, index=True),
    Column('conversation_id', String(32), nullable=False),
    Column('request_id', String(80), nullable=False),
    Column('actor', String(80), nullable=False, index=True),
    Column('tool_name', String(80), nullable=False),
    Column('application_id', String(100), nullable=True, index=True),
    Column('tool_call_id', String(100), nullable=False),
    Column('status', String(32), nullable=False),
    Column('reason', String(80), nullable=True),
    Column('duration_ms', Integer, nullable=True))


class AuditStore:
    def __init__(self, engine=None):
        self.engine = engine or get_engine()

    def begin(self, context, name, application_id, call_id):
        identifier = uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(insert(events).values(event_id=identifier, occurred_at=datetime.now(timezone.utc),
                run_id=context.run_id, conversation_id=context.conversation_id, request_id=context.request_id,
                actor=context.actor, tool_name=name[:80], application_id=application_id, tool_call_id=call_id[:100], status='started'))
        return identifier

    def finish(self, identifier, status, reason, duration_ms):
        with self.engine.begin() as conn:
            result = conn.execute(update(events).where(events.c.event_id == identifier).values(
                status=status, reason=reason, duration_ms=duration_ms))
            if result.rowcount != 1:
                raise RuntimeError('audit event missing')

    def query(self, context, actor=None, application_id=None, run_id=None, start=None, limit=100):
        if context.role != 'demo_admin':
            raise PermissionError('not authorized')
        query = select(events).order_by(events.c.occurred_at.desc()).limit(min(max(limit, 1), 100))
        for column, value in ((events.c.actor, actor), (events.c.application_id, application_id),
                              (events.c.run_id, run_id), (events.c.occurred_at, start)):
            if value is not None:
                query = query.where(column >= value if column is events.c.occurred_at else column == value)
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(query).mappings()]
