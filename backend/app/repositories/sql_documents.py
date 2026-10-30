"""材料元数据、版本和解析结果入库；文件仍使用原目录。"""
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import DATA_ROOT
from app.db.models import ApplicationRow, MaterialRow
from app.db.session import get_engine
from app.documents.parsers import parse_document


class SQLDocumentStore:
    def __init__(self):
        self.directory = Path(os.environ.get('CREDIT_DOCUMENT_ROOT', str(DATA_ROOT / 'documents')))

    def list(self, application):
        with Session(get_engine()) as session:
            return [row.payload for row in session.scalars(select(MaterialRow).where(
                MaterialRow.application_id == application, MaterialRow.source == 'upload').order_by(MaterialRow.category, MaterialRow.version))]

    def get(self, application, identifier):
        with Session(get_engine()) as session:
            row = session.get(MaterialRow, identifier)
            return row.payload if row and row.application_id == application and row.source == 'upload' else None

    def upload(self, application, category, filename, content):
        if not filename or filename != Path(filename).name or '/' in filename or '\\' in filename:
            raise ValueError('无效文件名')
        if Path(filename).suffix.lower() not in ('.pdf', '.docx') or not content or len(content) > 10 * 1024 * 1024:
            raise ValueError('仅允许非空PDF/DOCX，最大10MB')
        try:
            parsed = parse_document(content, filename)
        except Exception:
            parsed = dict(status='failed', sections=[], fields={}, error='文件无法解析，请重新提交可读取版本。', parser_version='label-v1')
        digest = hashlib.sha256(content).hexdigest()
        created_file = None
        try:
            with Session(get_engine()) as session, session.begin():
                application_row = session.scalar(select(ApplicationRow).where(ApplicationRow.id == application).with_for_update())
                if application_row is None:
                    raise ValueError('申请不存在')
                latest = session.scalar(select(MaterialRow).where(MaterialRow.application_id == application,
                    MaterialRow.category == category, MaterialRow.source == 'upload').order_by(MaterialRow.version.desc()).limit(1))
                if latest and latest.payload['sha256'] == digest:
                    return latest.payload
                version = (session.scalar(select(func.max(MaterialRow.version)).where(
                    MaterialRow.application_id == application, MaterialRow.category == category)) or 0) + 1
                identifier = uuid4().hex
                self.directory.mkdir(parents=True, exist_ok=True)
                created_file = self.directory / identifier
                with created_file.open('xb') as stream:
                    stream.write(content)
                payload = dict(id=identifier, application_id=application, category=category, version=version,
                    filename=filename, sha256=digest, parsed=parsed, unified_version=True)
                session.add(MaterialRow(id=identifier, application_id=application, category=category,
                    version=version, source='upload', payload=payload))
            return payload
        except Exception:
            # 普通事务失败删除本次新建文件；进程突然终止留下的孤立文件需运维核对。
            if created_file is not None:
                created_file.unlink(missing_ok=True)
            raise
