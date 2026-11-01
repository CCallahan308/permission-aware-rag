-- PostgreSQL DDL: Permission-Aware Multi-Tenant Schema with pgvector and Row-Level Security

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tenants table: distinct hospital networks
CREATE TABLE IF NOT EXISTS hospital_tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    subdomain VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Users table with assigned hospital tenant and role claims
CREATE TABLE IF NOT EXISTS hospital_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES hospital_tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('physician', 'nurse', 'billing_specialist', 'auditor')),
    clearance_level INT NOT NULL DEFAULT 1 CHECK (clearance_level BETWEEN 1 AND 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES hospital_tenants(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('ehr_clinical_note', 'clinical_guideline', 'billing_schedule', 'compliance_audit')),
    classification_level INT NOT NULL DEFAULT 1 CHECK (classification_level BETWEEN 1 AND 4),
    allowed_roles VARCHAR(50)[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Document chunks table with embeddings
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES hospital_tenants(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    allowed_roles VARCHAR(50)[] NOT NULL,
    classification_level INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_tenant_roles 
ON document_chunks (tenant_id, classification_level);

CREATE INDEX IF NOT EXISTS idx_chunks_roles_gin 
ON document_chunks USING gin (allowed_roles);

CREATE INDEX IF NOT EXISTS idx_docs_tenant 
ON documents (tenant_id, classification_level);

-- 7. Enable and enforce Row-Level Security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;

-- Drop prior policies if recreating
DROP POLICY IF EXISTS rls_chunk_tenant_isolation ON document_chunks;
DROP POLICY IF EXISTS rls_chunk_insert ON document_chunks;
DROP POLICY IF EXISTS rls_document_tenant_isolation ON documents;
DROP POLICY IF EXISTS rls_document_insert ON documents;

-- Hard tenant isolation policy for document chunks
CREATE POLICY rls_chunk_tenant_isolation ON document_chunks
FOR SELECT
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::UUID
    AND allowed_roles && string_to_array(current_setting('app.current_roles', true), ',')::VARCHAR[]
    AND classification_level <= COALESCE(NULLIF(current_setting('app.current_clearance', true), '')::INT, 1)
);

CREATE POLICY rls_chunk_insert ON document_chunks
FOR INSERT
WITH CHECK (true);

-- Hard tenant isolation policy for documents
CREATE POLICY rls_document_tenant_isolation ON documents
FOR SELECT
USING (
    tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::UUID
    AND allowed_roles && string_to_array(current_setting('app.current_roles', true), ',')::VARCHAR[]
    AND classification_level <= COALESCE(NULLIF(current_setting('app.current_clearance', true), '')::INT, 1)
);

CREATE POLICY rls_document_insert ON documents
FOR INSERT
WITH CHECK (true);

-- 8. Cryptographic tamper-evident audit log table
CREATE TABLE IF NOT EXISTS retrieval_audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    user_role VARCHAR(50) NOT NULL,
    query_text_sha256 VARCHAR(64) NOT NULL,
    filter_applied TEXT NOT NULL,
    retrieved_chunk_ids UUID[] NOT NULL,
    execution_duration_ms NUMERIC(8, 2) NOT NULL,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('PERMIT', 'EMPTY', 'DENY')),
    previous_record_hash VARCHAR(64) NOT NULL,
    record_hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_time 
ON retrieval_audit_log (tenant_id, event_time DESC);

-- 9. Role permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_user') THEN
        GRANT ALL ON ALL TABLES IN SCHEMA public TO rag_user;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO rag_user;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rag_user;
    END IF;
END $$;
