ALTER TABLE atlas_agent.checkpoints
    ADD COLUMN legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE atlas_agent.checkpoint_tombstones
    ADD COLUMN legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX atlas_checkpoints_purge_candidates_idx
    ON atlas_agent.checkpoints (retention_until, execution_id, token_digest)
    WHERE retention_until IS NOT NULL;

CREATE INDEX atlas_tombstones_purge_candidates_idx
    ON atlas_agent.checkpoint_tombstones (retention_until, execution_id, token_digest);

CREATE TABLE atlas_agent.checkpoint_purge_audit (
    audit_id UUID PRIMARY KEY,
    purge_run_id UUID NOT NULL,
    operation_id UUID NOT NULL UNIQUE,
    checkpoint_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    tenant_id TEXT,
    record_kind TEXT NOT NULL CHECK (record_kind IN ('checkpoint', 'tombstone')),
    outcome TEXT NOT NULL CHECK (
        outcome IN ('purged', 'skipped', 'blocked', 'failed')
    ),
    reason_code TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX atlas_checkpoint_purge_audit_run_idx
    ON atlas_agent.checkpoint_purge_audit (purge_run_id, operation_id);

CREATE INDEX atlas_checkpoint_purge_audit_tenant_idx
    ON atlas_agent.checkpoint_purge_audit (tenant_id, occurred_at)
    WHERE tenant_id IS NOT NULL;
