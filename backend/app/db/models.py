"""业务表定义；外键保护申请关联，JSON保留现有接口的嵌套结构。"""
from sqlalchemy import Column, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EnterpriseRow(Base):
    __tablename__ = 'enterprises'
    id = Column(String(100), primary_key=True)
    payload = Column(JSON, nullable=False)


class ApplicationRow(Base):
    __tablename__ = 'applications'
    id = Column(String(100), primary_key=True)
    enterprise_id = Column(String(100), ForeignKey('enterprises.id'), nullable=False, index=True)
    status = Column(String(60), nullable=False)
    submitted_at = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (Index('ix_application_status_time', 'status', 'submitted_at'),)


class MaterialRow(Base):
    __tablename__ = 'materials'
    id = Column(String(100), primary_key=True)
    application_id = Column(String(100), ForeignKey('applications.id'), nullable=False, index=True)
    category = Column(String(150), nullable=False)
    version = Column(Integer, nullable=False)
    source = Column(String(20), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint('application_id', 'category', 'version', name='uq_material_version'),)


class ReportRow(Base):
    __tablename__ = 'reports'
    id = Column(String(100), primary_key=True)
    application_id = Column(String(100), ForeignKey('applications.id'), nullable=False)
    generated_at = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (Index('ix_report_application_time', 'application_id', 'generated_at'),)


class StatusRow(Base):
    __tablename__ = 'status_events'
    id = Column(String(100), primary_key=True)
    application_id = Column(String(100), ForeignKey('applications.id'), nullable=False)
    occurred_at = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (Index('ix_event_application_time', 'application_id', 'occurred_at'),)


class ReviewRow(Base):
    __tablename__ = 'review_actions'
    id = Column(String(100), primary_key=True)
    application_id = Column(String(100), ForeignKey('applications.id'), nullable=False)
    report_id = Column(String(100), ForeignKey('reports.id'), nullable=True)
    sequence = Column(Integer, nullable=False)
    occurred_at = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (UniqueConstraint('application_id', 'sequence', name='uq_review_sequence'),
                      Index('ix_review_application_time', 'application_id', 'occurred_at'))


class MaterialCheckRow(Base):
    __tablename__ = 'material_checks'
    id = Column(String(100), primary_key=True)
    application_id = Column(String(100), ForeignKey('applications.id'), nullable=False)
    checked_at = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (Index('ix_material_checks_application_time', 'application_id', 'checked_at'),)


class ApprovalRow(Base):
    __tablename__ = 'approval_actions'
    id = Column(String(100), primary_key=True)
    application_id = Column(String(100), ForeignKey('applications.id'), nullable=False)
    occurred_at = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    __table_args__ = (Index('ix_approval_application_time', 'application_id', 'occurred_at'),)


class OperationAuditRow(Base):
    __tablename__ = 'operation_audit'
    id = Column(String(64), primary_key=True)
    occurred_at = Column(String(40), nullable=False)
    actor_id = Column(String(80), nullable=False)
    actor_role = Column(String(32), nullable=False)
    object_type = Column(String(32), nullable=False)
    object_id = Column(String(100), nullable=False)
    action = Column(String(64), nullable=False)
    before_value = Column(JSON, nullable=True)
    after_value = Column(JSON, nullable=True)
    result = Column(String(24), nullable=False)
    reason_code = Column(String(40), nullable=True)
    __table_args__ = (Index('ix_operation_audit_object_time', 'object_type', 'object_id', 'occurred_at'),
                      Index('ix_operation_audit_actor_time', 'actor_id', 'occurred_at'))


class KnowledgeRow(Base):
    __tablename__ = 'knowledge_items'
    id = Column(String(100), primary_key=True)
    version = Column(String(50), primary_key=True)
    payload = Column(JSON, nullable=False)


class MigrationRow(Base):
    __tablename__ = 'schema_migrations'
    id = Column(String(100), primary_key=True)
    fingerprint = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
