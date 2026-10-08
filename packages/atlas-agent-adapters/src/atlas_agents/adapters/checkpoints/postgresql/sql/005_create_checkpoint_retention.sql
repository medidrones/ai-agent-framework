ALTER TABLE atlas_agent.checkpoints
    ADD COLUMN retention_class TEXT NOT NULL DEFAULT 'waiting_for_approval',
    ADD COLUMN retention_until TIMESTAMPTZ,
    ADD COLUMN retention_policy_version TEXT;

ALTER TABLE atlas_agent.checkpoints
    ADD CONSTRAINT atlas_checkpoint_retention_class_valid CHECK (
        retention_class IN ('active', 'waiting_for_approval', 'expired', 'terminal')
    );

CREATE INDEX atlas_checkpoints_retention_idx
    ON atlas_agent.checkpoints (retention_until, execution_id)
    WHERE retention_until IS NOT NULL;

CREATE TABLE atlas_agent.checkpoint_tombstones (
    token_digest BYTEA PRIMARY KEY,
    execution_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tenant_id TEXT,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    retention_until TIMESTAMPTZ NOT NULL,
    retention_policy_version TEXT NOT NULL,
    fencing_token BIGINT,
    CONSTRAINT atlas_tombstone_retention_order
        CHECK (retention_until >= consumed_at),
    CONSTRAINT atlas_tombstone_fencing_positive
        CHECK (fencing_token IS NULL OR fencing_token > 0)
);

CREATE INDEX atlas_checkpoint_tombstones_retention_idx
    ON atlas_agent.checkpoint_tombstones (retention_until, execution_id);

CREATE INDEX atlas_checkpoint_tombstones_tenant_idx
    ON atlas_agent.checkpoint_tombstones (tenant_id)
    WHERE tenant_id IS NOT NULL;

ALTER TABLE atlas_agent.execution_recovery_attempts
    ADD COLUMN retention_until TIMESTAMPTZ,
    ADD COLUMN retention_policy_version TEXT;
