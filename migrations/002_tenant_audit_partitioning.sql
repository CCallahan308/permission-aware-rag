-- Independent logical hash chains use the existing audit table and RLS policies.
-- One B-tree supports both ascending verification and descending tip lookup.
CREATE INDEX IF NOT EXISTS idx_audit_tenant_id_desc
ON retrieval_audit_log (tenant_id, id DESC);

-- Do not rewrite or silently bless historical hashes. An older global chain
-- requires an operator-reviewed archival/cutover plan before this migration.
-- Payload integrity remains the Python verifier's responsibility.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT previous_record_hash,
                   COALESCE(
                       LAG(record_hash) OVER (PARTITION BY tenant_id ORDER BY id),
                       repeat('0', 64)
                   ) AS expected_previous
            FROM retrieval_audit_log
        ) AS tenant_chain
        WHERE previous_record_hash <> expected_previous
    ) THEN
        RAISE EXCEPTION 'Audit history is not a continuous tenant-partitioned chain. Preserve the original history and perform an operator-reviewed cutover; hashes were not rewritten.';
    END IF;
END $$;
