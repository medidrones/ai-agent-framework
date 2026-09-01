# Contratos fundamentais do core

Esta referência descreve a API pública introduzida para representar agentes e
seus dados de execução. Os modelos são independentes de provider e
infraestrutura. Eles não executam modelos, resolvem anexos ou persistem dados.

Todos os modelos descritos abaixo são imutáveis no nível do contrato Pydantic,
rejeitam campos extras e usam factories independentes para dicionários. Os
metadados devem ser serializáveis em JSON.

## `Agent`

Contrato abstrato e genérico implementado por agentes concretos:

- `definition` retorna uma `AgentDefinition`;
- `run` é assíncrono e retorna `AgentResult[TOutput]`;
- `stream` retorna diretamente um `AsyncIterator[AgentEvent]` e pode ser
  implementado como async generator.

O contrato não fornece runtime, loop de modelo ou gerenciamento de lifecycle.

## `AgentDefinition`

Descreve a configuração estática de um agente por `agent_id`, `name`,
`description`, `instructions` e `metadata`. Identificador, nome e instruções
não podem estar vazios nem conter somente espaços.

## `AgentInput` e `AgentAttachment`

`AgentInput` transporta uma mensagem, uma tupla de anexos e metadados.
Mensagens vazias são permitidas para possibilitar entradas compostas somente
por anexos.

`AgentAttachment` contém uma referência opaca por `uri`, acompanhada por
identificador, nome, tipo de mídia e metadados. O core não interpreta protocolos
nem acessa o conteúdo apontado pela URI.

## `AgentContext` e `ExecutionIdentity`

`AgentContext` recebe o `execution_id` obrigatório criado pelo consumidor.
Sessão, usuário, tenant e identidade são opcionais, permitindo execuções batch,
workers e integrações máquina-máquina.

`ExecutionIdentity` representa uma identidade já resolvida por `subject`,
`roles`, `permissions` e `attributes`. O modelo não conhece OAuth, JWT nem
qualquer produto de identidade.

## `ExecutionStatus`

Enumera os estados públicos iniciais:

```text
CREATED
RUNNING
WAITING
COMPLETED
FAILED
CANCELLED
TIMED_OUT
LIMIT_EXCEEDED
BUDGET_EXCEEDED
REJECTED
```

O enum não implementa transições ou máquina de estados.

## `AgentResult[TOutput]`

Snapshot genérico composto por identificador da execução, status, saída
opcional, uso, eventos e erro opcional. As invariantes atuais são deliberadamente
mínimas:

- um resultado `COMPLETED` não pode conter erro;
- um resultado `FAILED` deve conter erro;
- um resultado `CANCELLED` pode omitir saída e erro.

## `Usage`

Registra `input_tokens`, `output_tokens` e `estimated_cost`. Contagens e custo
não podem ser negativos. `estimated_cost` utiliza `Decimal` e não aplica tabela
de preços. `total_tokens` é uma propriedade calculada como a soma da entrada e
da saída, evitando estado duplicado.

## `AgentErrorInfo`

Representa um erro seguro por `code`, `message`, `retryable` e `details`. O
modelo não transporta exceptions concretas, stack traces ou credenciais. O
código não pode estar vazio e deve ser adequado para automação; a mensagem não
pode estar vazia e deve ser adequada para leitura humana.

## `AgentEvent` e `AgentEventType`

`AgentEvent` é um snapshot serializável contendo IDs opacos, sequência não
negativa, tipo, timestamp e dados. O timestamp deve possuir fuso horário; o core
não cria timestamps automaticamente.

Os tipos iniciais se limitam a criação, início, conclusão, falha e cancelamento
de uma execução. Eventos de modelos, ferramentas, memória ou guardrails ainda
não existem.

## Importação

As APIs intencionais podem ser importadas diretamente do namespace principal:

```python
from atlas_agents import (
    Agent,
    AgentAttachment,
    AgentContext,
    AgentDefinition,
    AgentErrorInfo,
    AgentEvent,
    AgentEventType,
    AgentInput,
    AgentResult,
    ExecutionIdentity,
    ExecutionStatus,
    Usage,
)
```
