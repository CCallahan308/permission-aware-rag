import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    BigInteger,
    Numeric,
    func
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
from app.database import Base

class HospitalTenant(Base):
    __tablename__ = "hospital_tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    subdomain = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class HospitalUser(Base):
    __tablename__ = "hospital_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospital_tenants.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), nullable=False)
    clearance_level = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospital_tenants.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False)
    classification_level = Column(Integer, nullable=False, default=1)
    allowed_roles = Column(ARRAY(String(50)), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospital_tenants.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384), nullable=False)
    allowed_roles = Column(ARRAY(String(50)), nullable=False)
    classification_level = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class RetrievalAuditLog(Base):
    __tablename__ = "retrieval_audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    user_role = Column(String(50), nullable=False)
    query_text_sha256 = Column(String(64), nullable=False)
    filter_applied = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    execution_duration_ms = Column(Numeric(8, 2), nullable=False)
    decision = Column(String(20), nullable=False)
    previous_record_hash = Column(String(64), nullable=False)
    record_hash = Column(String(64), nullable=False)
