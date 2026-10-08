CREATE TABLE atlas_agent.execution_recovery_attempts (
    attempt_id UUID PRIMARY KEY,
    execution_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    fencing_token BIGINT NOT NULL CHECK (fencing_token > 0),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    outcome TEXT,
    reason_code TEXT,
    CONSTRAINT atlas_recovery_attempt_number_unique
        UNIQUE (execution_id, checkpoint_id, attempt_number),
    CONSTRAINT atlas_recovery_completion_consistent CHECK (
        (completed_at IS NULL AND outcome IS NULL)
        OR (completed_at IS NOT NULL AND outcome IS NOT NULL)
    )
);

CREATE INDEX atlas_recovery_attempts_execution_idx
    ON atlas_agent.execution_recovery_attempts (
        execution_id, checkpoint_id, attempt_number DESC
    );
