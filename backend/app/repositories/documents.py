"""Unified runtime document repository; no implicit legacy SQLite selection."""
from app.core.config import DATA_ROOT
from app.repositories.sql_documents import SQLDocumentStore as DocumentStore

ROOT = DATA_ROOT / "documents"
LIMIT = 10 * 1024 * 1024
