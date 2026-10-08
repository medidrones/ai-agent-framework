# Semântica de versionamento

## Dois campos, duas responsabilidades

| Campo | Responsabilidade | Evolução |
| --- | --- | --- |
| `checkpoint_version` | formato de `ExecutionCheckpoint` | muda somente com evolução compatível do schema do payload |
| `revision` | revisão da linha PostgreSQL | inicia em 1 e incrementa em cada CAS confirmado |

Usar `checkpoint_version` como token de concorrência corromperia a negociação do
formato público e foi expressamente rejeitado.

## Regras de revisão

- Migration 002 adiciona `revision BIGINT NOT NULL DEFAULT 1`.
- A constraint exige valor positivo.
- A aplicação nunca fornece a nova revisão; o SQL executa `revision + 1`.
- Revisão esperada zero ou negativa é rejeitada antes de acessar o banco.
- Leitura, conflito, expiração, cancelamento e rollback não incrementam.
- Não existe operação pública para reduzir ou definir arbitrariamente a
  revisão.

## Registros anteriores

Ao aplicar a migration 002, linhas existentes recebem revisão 1. Isso preserva
payload, token digest, datas e identificadores da DS-002.
