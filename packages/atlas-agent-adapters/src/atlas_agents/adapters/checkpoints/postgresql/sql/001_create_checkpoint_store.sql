CREATE TABLE atlas_agent.checkpoints (
    token_digest BYTEA PRIMARY KEY,
    checkpoint_version INTEGER NOT NULL CHECK (checkpoint_version > 0),
    execution_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    tenant_id TEXT,
    payload JSONB NOT NULL,
    checkpoint_created_at TIMESTAMPTZ NOT NULL,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,
    CONSTRAINT atlas_checkpoint_expiration_order
        CHECK (expires_at IS NULL OR expires_at >= checkpoint_created_at)
);

CREATE INDEX atlas_checkpoints_execution_id_idx
    ON atlas_agent.checkpoints (execution_id);

CREATE INDEX atlas_checkpoints_tenant_id_idx
    ON atlas_agent.checkpoints (tenant_id)
    WHERE tenant_id IS NOT NULL;

CREATE INDEX atlas_checkpoints_expires_at_idx
    ON atlas_agent.checkpoints (expires_at)
    WHERE expires_at IS NOT NULL;
