CREATE INDEX atlas_checkpoints_recovery_candidates_idx
    ON atlas_agent.checkpoints (
        checkpoint_created_at, execution_id, token_digest
    );
