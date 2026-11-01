-- The runtime connection must not own tables or bypass RLS. Provision its
-- login/password separately; migration credentials never serve retrieval.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_user') THEN
        IF EXISTS (
            SELECT 1 FROM pg_roles
            WHERE rolname = 'rag_user' AND (rolsuper OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'rag_user must be NOSUPERUSER NOBYPASSRLS';
        END IF;
        REVOKE ALL ON hospital_users, hospital_tenants, documents,
                      document_chunks, retrieval_audit_log FROM rag_user;
        GRANT SELECT ON hospital_tenants, documents, document_chunks,
                        retrieval_audit_log TO rag_user;
        GRANT INSERT ON documents, document_chunks, retrieval_audit_log TO rag_user;
        -- SELECT FOR NO KEY UPDATE requires UPDATE on at least one column.
        GRANT UPDATE (id) ON hospital_tenants TO rag_user;
        REVOKE ALL ON SEQUENCE retrieval_audit_log_id_seq FROM rag_user;
        GRANT USAGE ON SEQUENCE retrieval_audit_log_id_seq TO rag_user;
        IF to_regclass('schema_migrations') IS NOT NULL THEN
            REVOKE ALL ON schema_migrations FROM rag_user;
        END IF;
    END IF;
END $$;
