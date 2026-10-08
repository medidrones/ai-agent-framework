# Análise de concorrência

## Garantia normativa atual

`CheckpointStore.consume()` deve recuperar o checkpoint e invalidar o token na
mesma operação atômica. O teste
`test_same_token_can_be_consumed_by_only_one_concurrent_resume` demonstra, com
o fake protegido por `asyncio.Lock`, uma retomada vencedora, uma rejeitada e
uma única execução da ferramenta.

Essa evidência certifica a semântica do core e do fake no mesmo processo; não
certifica atomicidade distribuída. PostgreSQL deverá usar operação condicional
transacional. Redis deverá usar operação atômica única ou script Lua, sem
sequência `GET`/`DEL` separada.

## Janelas de falha

1. Falha antes de `save`: nenhuma suspensão é entregue.
2. Falha depois de `save`: token e checkpoint podem ser retomados.
3. Falha durante `consume`: o contrato não permite saber se houve consumo.
4. Falha após `consume`, antes da ferramenta: token perdido e trabalho pendente.
5. Falha durante/depois do efeito externo: não há receipt transacional ou chave
   de idempotência exigida pelo contrato.

Portanto, “um token, um consumidor” não equivale a “efeito externo exatamente
uma vez”. Os adapters devem ser fail-closed e não podem prometer mais do que
conseguem provar.

## Ausências

Não existem revisão/ETag, compare-and-set, lease, ownership, fencing token ou
estado intermediário de consumo. Lacunas relacionadas: `DS001-GAP-001`,
`DS001-GAP-002`, `DS001-GAP-005`, `DS001-GAP-006` e `DS001-GAP-007`.
