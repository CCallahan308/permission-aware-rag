from datetime import datetime
from typing import Annotated, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, StrictInt, field_validator

Role = Literal["physician", "nurse", "billing_specialist", "auditor"]
ChunkText = Annotated[str, Field(min_length=1, max_length=65536)]

class UserContext(BaseModel):
    user_id: UUID
    tenant_id: UUID
    roles: List[Role] = Field(min_length=1, max_length=4)
    clearance: StrictInt = Field(ge=1, le=4)

class ChunkResult(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    similarity: float

class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The user query string")
    top_k: int = Field(default=5, ge=1, le=50, description="Top K chunks to return")
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum cosine similarity cutoff")
    tenant_id: Optional[UUID] = Field(default=None, description="Untrusted client body parameter")
    generate_answer: bool = Field(default=False, description="Whether to invoke grounded generation pipeline")

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must contain non-whitespace text")
        return value

class RetrieveResponse(BaseModel):
    query: str
    total_matched: int
    chunks: List[ChunkResult]
    audit_record_hash: Optional[str] = None
    assembled_context: Optional[str] = None
    answer: Optional[str] = None
    cited_chunk_ids: Optional[List[UUID]] = None
    citation_verification_passed: Optional[bool] = None

class TokenRequest(BaseModel):
    tenant_id: UUID
    email: str
    role: Role
    clearance_level: int = Field(default=1, ge=1, le=4)
    user_id: Optional[UUID] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    claims: UserContext

class DocumentChunkInput(BaseModel):
    content: str
    chunk_index: int
    allowed_roles: List[str]
    classification_level: int = 1

class DocumentCreate(BaseModel):
    tenant_id: UUID
    title: str = Field(min_length=1, max_length=255)
    document_type: Literal["ehr_clinical_note", "clinical_guideline", "billing_schedule", "compliance_audit"]
    classification_level: StrictInt = Field(ge=1, le=4)
    allowed_roles: List[Role] = Field(min_length=1, max_length=4)
    chunks: List[ChunkText] = Field(min_length=1, max_length=50)

class AuditVerificationRecord(BaseModel):
    id: int
    event_time: datetime
    tenant_id: UUID
    user_id: UUID
    decision: str
    is_valid: bool
    expected_hash: str
    stored_hash: str

class AuditVerificationReport(BaseModel):
    total_records: int
    is_chain_intact: bool
    violation_record_id: Optional[int] = None
    details: str
