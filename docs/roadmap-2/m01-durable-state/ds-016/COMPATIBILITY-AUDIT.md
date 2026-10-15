# Auditoria de compatibilidade

| Dimensão | Verificação | Resultado |
| --- | --- | --- |
| Python | 3.12 local; CI 3.12/3.13 Windows/Linux | PASS |
| API pública | contratos mínimos 1.x preservados | PASS |
| capabilities | aditivas e detectadas estruturalmente | PASS |
| serialização | fixtures 1.0.1 e versões explícitas | PASS |
| distribuição | `Requires-Python >=3.12`, `py.typed`, licença | PASS |
| namespace | coexistência dos sete pacotes | PASS |
| extras | PostgreSQL/Redis fora do core | PASS |
| plugins | entry point OpenAI preservado | PASS |
| migrations | upgrade/rolling/rollback documentados | PASS |

A instalação limpa dos wheels publicados 1.0.1 foi validada em três ambientes:
core mínimo, extensões-base sem extras e distribuição completa. `uv pip check`
não encontrou inconsistências. Os wheels candidatos de core e adapters também
foram reconstruídos com sucesso a partir de `89f00df`.

**Decisão:** `BACKWARD_COMPATIBILITY = VERIFIED`.
