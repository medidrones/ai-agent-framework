# Arquitetura

O Atlas Agent Framework é organizado como um monorepo Python. Sua arquitetura
se baseia em inversão de dependência: contratos estáveis do core são
implementados por pacotes opcionais de infraestrutura.

```text
Consumidores
    ↓
Adapters
    ↓
Contratos do core
    ↑
Providers implementam os contratos
```

O core não importa adapters nem providers concretos. Providers e adapters
dependem dos contratos públicos do core e permanecem substituíveis.

## Camadas

1. **Core** define contratos neutros de provedor para agentes, modelos,
   ferramentas, memória, conhecimento, orquestração, governança e
   observabilidade.
2. **Plugins** implementam os contratos do core para provedores e
   infraestruturas concretos.
3. **Adapters** expõem o framework por transportes como CLI, MCP, REST, gRPC ou
   eventos.
4. **Consumidores** integram o Atlas por sua API Python ou por um adapter.

As dependências apontam para dentro. O core deve continuar utilizável sem
plugins ou adapters e nunca deve importar esses pacotes.

## Política async-first

Operações que realizam I/O devem expor APIs assíncronas. Wrappers síncronos
podem ser oferecidos como conveniência, mas não definem os contratos primários.

## Lifecycle de execução

`ExecutionLifecycle` encapsula o status corrente. Não existe setter público:
Toda alteração passa por um mapa declarativo, produz uma
`ExecutionTransition` imutável e entra no histórico ordenado. Estados terminais
são centralizados e não possuem transições de saída. Toda instância nova inicia
em `CREATED`; `ExecutionLifecycle.restore()` é usado exclusivamente pela
restauração validada de checkpoints.

O lifecycle não conhece event bus ou observabilidade. `AgentEventFactory`
transforma transições em eventos separadamente, mantendo sequência local por
execução. Essa separação evita acoplar regras de estado ao transporte futuro de
eventos.

## Abstração de modelos

`ModelProvider` é a porta async-first usada para listar modelos, gerar respostas
completas e produzir streaming estruturado. Requests, responses, mensagens
multimodais, tool calls, usage e erros pertencem ao vocabulário do Atlas e não
expõem objetos de SDKs externos.

Providers concretos dependem do core e do SDK que adaptam. O core nunca depende
do provider. `ModelExecutionContext` limita a fronteira aos identificadores de
correlação necessários, sem entregar todo o `AgentContext` à integração.

`ModelProviderRegistry` recebe providers por injeção explícita e mantém estado
somente em sua instância. A descoberta produz catálogo imutável, e a seleção
separa filtros obrigatórios da strategy de ranking. O resultado contém IDs e
descriptor, não a instância runtime do provider.

## Estado de execução

`ExecutionState` é a fonte de verdade interna de uma execução e reutiliza uma
única instância de `ExecutionLifecycle`. Ele guarda referências aos contratos
imutáveis de definição, entrada e contexto e controla mensagens, seleção,
contadores, uso, eventos, output, erro e timestamps. Não armazena provider,
registry, serviços ou credenciais e não realiza I/O.

As coleções não são expostas como listas mutáveis. Toda mutação operacional
passa por métodos explícitos e é bloqueada depois de um estado terminal;
eventos permanecem anexáveis como journal de observabilidade. `snapshot()`
produz uma observação frozen e isolada, enquanto `to_result()` só produz um
`AgentResult` quando o lifecycle é terminal.

`AgentRuntime` é o único proprietário do execution loop. Ele cria um estado por
chamada, seleciona o modelo uma vez pelo registry e constrói requests
provider-neutral para cada turn. Respostas `TOOL_CALL` acionam tools permitidas,
e seus resultados retornam ao mesmo provider/model no histórico da conversa.
No modo incremental, um acumulador por turn valida o protocolo e reconstrói a
mesma `ModelResponse` usada pelo loop. `Agent.run()`
e `Agent.stream()` permanecem fachadas públicas e deverão delegar ao runtime,
sem implementar um segundo loop. A decisão está registrada no
[`ADR-001`](docs/adr/ADR-001-agent-runtime-execution-ownership.md).

O runtime deriva somente capabilities necessárias ao input, normaliza erros
para `AgentErrorInfo` e preserva cancelamento cooperativo. Providers e registry
continuam transitórios: nenhuma instância de infraestrutura entra no state ou
no result.

`ExecutionLimits` e `ExecutionBudget` configuram políticas por execução.
`ExecutionLimitChecker` avalia contadores, usage e custo sem mutar estado; o
runtime mantém ownership das transições `LIMIT_EXCEEDED` e `BUDGET_EXCEEDED`.
Um deadline absoluto baseado em relógio monotônico governa seleção e invocação
nos modos completo e incremental. Ele não converte timeout do provider nem
cancelamento externo em timeout do runtime.

## Ferramentas

`ToolDefinition` representa o contrato completo de runtime; sua conversão para
`ModelToolDefinition` expõe somente nome, descrição e parâmetros. Implementações
assíncronas de `Tool` recebem suas dependências no construtor e um
`ToolExecutionContext` restrito por chamada, sem service locator.

`ToolRegistry` armazena apenas ferramentas conhecidas, localmente e em ordem de
registro. `ToolExecutor` resolve nomes exatos, avalia permissões, valida
argumentos pelo JSON Schema Draft 2020-12 e normaliza output e erros. Ele não
possui estado por execução, retry, deduplicação, descoberta dinâmica ou acesso
à infraestrutura. O `AgentRuntime` integra a camada usando a allowlist de cada
agente, mantém deduplicação estritamente local no `ExecutionState` e executa
batches sequencialmente.

## Aprovação humana e retomada

`ToolDefinition.approval_mode` define se uma ferramenta dispensa aprovação, é
governada por `ApprovalPolicy` ou sempre exige decisão humana. O runtime avalia
aprovação somente depois de allowlist, permissão e validação, mas antes de
limite, contador e execução.

```text
Model TOOL_CALL
      ↓
ApprovalPolicy
  ├─ não → executar ferramenta
  └─ sim → ApprovalRequest
                ↓
        WAITING_FOR_APPROVAL
                ↓
        ExecutionCheckpoint
                ↓
          CheckpointStore
                ↓
            ResumeToken
                ↓
     AgentRuntime.resume()
       ├─ approve → executar e continuar
       └─ reject  → REJECTED
```

`ExecutionCheckpoint` contém somente contratos serializáveis. A implementação
de `CheckpointStore` é injetada pelo consumidor e deve consumir tokens
atomicamente. `ExecutionStateRestorer` valida a versão e reconstrói lifecycle,
eventos, seleção, mensagens, contadores, uso, limites, budget e timeout
restante. Providers, ferramentas, registries e deadlines monotônicos absolutos
não são persistidos.

## Independência de infraestrutura

O core não depende de SDKs de modelos, frameworks web, bancos de dados,
message brokers ou bancos vetoriais. Cada integração pertence a uma distribuição
opcional e recebe configuração e credenciais por injeção explícita.

## Política de plugins

Plugins implementam contratos pequenos e neutros definidos pelo core. Uma
integração pode depender do SDK que adapta, mas essa dependência não pode vazar
para a instalação do pacote core nem para suas interfaces públicas.

## Qualidade e segurança

Todo pacote deve passar por lint, formatação, tipagem estrita, testes e build.
Entradas externas são tratadas como não confiáveis; segredos não são globais,
registrados ou serializados; e execução arbitrária de código permanece fora do
core.

## Escopo atual

Atualmente, o repositório inclui o workspace e os contratos fundamentais do
pacote `atlas-agent-core`: agentes, lifecycle, eventos, estado de execução e
contratos abstratos de modelos, incluindo multimodalidade, streaming e a
interface `ModelProvider`.

Esses tipos representam snapshots imutáveis nas fronteiras do framework. IDs
são strings opacas e não impõem UUID. Metadados são explicitamente tipados,
isolados por instância e validados como serializáveis em JSON. Eventos exigem
timestamps com fuso horário.

O core já oferece execução multi-turn completa ou incremental por
`ModelProvider`, sem provider concreto, com limites, budget e timeout opcionais.
Também oferece contratos, registro e execução integrada de ferramentas.
Também oferece aprovação humana, checkpoints versionados e retomada segura por
storage abstrato. Retries, fallback, memória e integrações concretas de
armazenamento serão introduzidos incrementalmente em tarefas posteriores.

## Evolução prevista

Novas distribuições serão criadas somente quando houver contratos estáveis a
implementar. A evolução prevista inclui providers, memória, conhecimento, MCP,
observabilidade, avaliação e adapters de transporte, sempre como pacotes
opcionais ao redor do core.

Os limites detalhados dos pacotes estão documentados em
[`docs/architecture/dependency-rules.md`](docs/architecture/dependency-rules.md).

## Empacotamento do workspace

O projeto raiz coordena dependências e ferramentas, mas não é uma distribuição
publicável. Cada pacote possui seus próprios metadados e backend PEP 517. Como o
`uv build` usa o projeto raiz por padrão, builds executados na raiz selecionam o
pacote explicitamente com `uv build --package atlas-agent-core`.
