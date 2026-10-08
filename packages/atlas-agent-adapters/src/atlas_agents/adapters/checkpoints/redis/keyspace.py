"""Safe and deterministic Redis checkpoint key derivation."""

from __future__ import annotations

import hashlib
import hmac
import unicodedata

from atlas_agents.approvals import ResumeToken


class RedisCheckpointKeyspace:
    """Derive opaque single-slot keys from an explicit namespace and token."""

    def __init__(self, namespace: str, *, token_hmac_key: bytes | None = None) -> None:
        """Validate the namespace and configure optional keyed token hashing."""
        normalized = unicodedata.normalize("NFKC", namespace)
        if not normalized or normalized != normalized.strip():
            raise ValueError("O namespace Redis deve ser explícito e não vazio.")
        if len(normalized) > 128 or any(ord(char) < 32 for char in normalized):
            raise ValueError("O namespace Redis contém caracteres inválidos.")
        if token_hmac_key is not None and len(token_hmac_key) < 32:
            raise ValueError("A chave HMAC do token deve possuir ao menos 32 bytes.")
        self._namespace_digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        self._token_hmac_key = token_hmac_key

    @property
    def namespace_digest(self) -> str:
        """Return the non-reversible namespace identifier used in keys."""
        return self._namespace_digest

    def checkpoint_key(self, resume_token: ResumeToken) -> str:
        """Build one cluster-compatible key without exposing the resume token."""
        token = resume_token.value.encode("utf-8")
        digest = (
            hmac.digest(self._token_hmac_key, token, "sha256")
            if self._token_hmac_key is not None
            else hashlib.sha256(token).digest()
        )
        token_digest = digest.hex()
        # The per-checkpoint hash tag keeps every operation on one Cluster slot
        # without concentrating the complete namespace in a single slot.
        slot = f"{self._namespace_digest}:{token_digest}"
        return f"atlas:{{{slot}}}:checkpoint"
