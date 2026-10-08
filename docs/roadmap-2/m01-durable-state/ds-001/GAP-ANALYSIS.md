# Análise de lacunas

| ID | Componente | Severidade | Descrição / evidência | Impacto | Proposta | Compatibilidade | Destino |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `DS001-GAP-001` | Consumo/resume | CRITICAL | `runtime.py`: `consume` invalida antes da ferramenta | crash pode perder trabalho ou deixar efeito ambíguo | ADR para claim/idempotência, receipt/outbox ou recovery journal | a definir; pode ser additive ou breaking | decisão antes da DS-002 |
| `DS001-GAP-002` | Concorrência | HIGH | `CheckpointStore` não possui revisão, CAS, lease ou fencing | não há coordenação de ownership além do consumo | protocolo opcional de claim/revisão ou regra por adapter | additive | DS-002/DS-003 |
| `DS001-GAP-003` | Retenção | HIGH | checkpoint/store não possuem expiração, retention ou purge | acúmulo e políticas divergentes | definir TTL e cleanup separados da aprovação | additive | DS-002/DS-003 |
| `DS001-GAP-004` | Segurança | HIGH | lookup recebe apenas bearer token | isolamento/autorização de tenant não são verificáveis pelo core | definir obrigação e testes do adapter | additive | DS-002/DS-003 |
| `DS001-GAP-005` | `save` | HIGH | colisão e create-only não estão especificados | sobrescrita pode trocar trabalho associado ao token | exigir falha para token existente | additive/clarification | DS-002/DS-003 |
| `DS001-GAP-006` | Falhas de consumo | HIGH | teste certifica propagação bruta de erro; estado físico é desconhecido | retry pode ser inseguro | erro tipado e reconciliação/receipt | additive; semântica pode exigir versão | arquitetura durable-state |
| `DS001-GAP-007` | Validação de resume | MEDIUM | modo, versão e decisão são validados após consumo | entrada inválida elimina a capacidade de retry | decidir entre fail-closed atual e claim/ack | potencialmente breaking | ADR futura |
| `DS001-GAP-008` | Serialização | MEDIUM | somente Pydantic v1; sem codec ou upcaster | evolução de schema não tem migração definida | envelope canônico e política de versões | additive | durable-state |
| `DS001-GAP-009` | Recuperação | MEDIUM | `read/inspect/query` são `MISSING` | coordenador não enumera trabalho pendente | API administrativa separada | additive | tarefa futura |
| `DS001-GAP-010` | `ResumeToken` | MEDIUM | `repr(ResumeToken)` inclui `value` | logging acidental expõe bearer token | `repr=False` e teste de não exposição | additive/comportamental | segurança do core |
| `DS001-GAP-011` | Payload | MEDIUM | argumentos, mensagens e metadata podem conter segredos | vazamento em storage/log/backup | classificação, redaction e encryption guidance | additive | segurança/adapters |
| `DS001-GAP-012` | Operação | LOW | métricas administrativas, cleanup e listagem ausentes | operação depende de convenções locais | manter fora do core ou protocolo opcional | additive | tarefa futura |

## Compatibilidade

As propostas não autorizam mudança na API 1.x nesta certificação. Extensões
devem preferir protocolos opcionais/adapters e preservar `save/consume`. Se a
resolução da lacuna crítica exigir alteração incompatível, ela demanda ADR,
versionamento e decisão explícita antes da implementação.

## Contagem

- CRITICAL: 1
- HIGH: 5
- MEDIUM: 5
- LOW: 1
