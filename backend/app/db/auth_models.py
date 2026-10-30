"""账号与归属表；通过显式迁移创建，不在应用启动时自动建表。"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from app.db.models import Base


class UserRow(Base):
    __tablename__ = 'users'
    id = Column(String(64), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False)
    display_name = Column(String(100), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class LoginSessionRow(Base):
    __tablename__ = 'login_sessions'
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id'), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


class ApplicationOwnerRow(Base):
    __tablename__ = 'application_owners'
    application_id = Column(String(100), ForeignKey('applications.id'), primary_key=True)
    user_id = Column(String(64), ForeignKey('users.id'), nullable=False, index=True)
