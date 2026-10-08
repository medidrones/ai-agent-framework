# Taxonomia de falhas

`RecoveryFailureCategory` distingue infraestrutura transitória/permanente, crash de
processo, commit ambíguo, corrupção, perda de ownership, falha de autorização,
efeito externo desconhecido, cancellation e deadline excedido.

`ConservativeRecoverySafetyPolicy` não converte exceções genéricas em retry:

| Evidência durável | Decisão |
| --- | --- |
| terminal, cancelada ou deadline vencido | `TERMINAL`/`BLOCKED` |
| autorização ou ownership não verificados | `BLOCKED` |
| efeito externo desconhecido | `RECONCILIATION_REQUIRED` |
| efeito executado sem reconciliação | `RECONCILIATION_REQUIRED` |
| corrupção, commit ambíguo ou falha permanente | `BLOCKED` |
| estado confirmado, autorizado e owned | `SAFE_TO_RESUME` |

O teste parametrizado `test_safety_policy_is_fail_closed` comprova todas as saídas.
