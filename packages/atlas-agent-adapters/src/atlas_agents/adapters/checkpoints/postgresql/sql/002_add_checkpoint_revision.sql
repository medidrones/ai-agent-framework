ALTER TABLE atlas_agent.checkpoints
    ADD COLUMN revision BIGINT NOT NULL DEFAULT 1,
    ADD COLUMN modified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD CONSTRAINT atlas_checkpoint_revision_positive CHECK (revision > 0);
