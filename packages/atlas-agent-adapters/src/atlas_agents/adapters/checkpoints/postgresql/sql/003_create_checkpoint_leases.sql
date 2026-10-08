CREATE TABLE atlas_agent.checkpoint_leases (
    checkpoint_id TEXT PRIMARY KEY,
    owner_id TEXT,
    fencing_token BIGINT NOT NULL DEFAULT 0,
    acquired_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    CONSTRAINT atlas_checkpoint_lease_fencing_non_negative
        CHECK (fencing_token >= 0),
    CONSTRAINT atlas_checkpoint_lease_state_consistent CHECK (
        (owner_id IS NULL AND acquired_at IS NULL AND expires_at IS NULL)
        OR
        (owner_id IS NOT NULL AND acquired_at IS NOT NULL AND expires_at IS NOT NULL
         AND expires_at > acquired_at)
    )
);

CREATE INDEX atlas_checkpoint_leases_expiration_idx
    ON atlas_agent.checkpoint_leases (expires_at)
    WHERE owner_id IS NOT NULL;
