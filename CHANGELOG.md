# Registro de alterações

Todas as alterações relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- API de plugins com manifesto versionado, capabilities, contexto restrito e
  contribuições fortemente tipadas.
- Discovery determinístico pelo grupo `atlas_agents.plugins` usando
  `importlib.metadata`, sem import ou ativação automática.
- Loader de factory canônica, registry local de plugins e introspecção sem
  configuração ou objetos implementadores.
- Ativação explícita com compatibility check, descrição livre de efeitos,
  preflight de conflitos, validação de protocolo e rollback em ordem inversa.
- Registro opcional de providers, tools, guardrails e evaluators nos registries
  injetados; Memory, Knowledge e Observability permanecem host-managed.
- Desativação, reativação, preservação de cancelamento e documentação de
  autoria, segurança e arquitetura do ecossistema de plugins.

- Distribuição opcional `atlas-agent-evaluation`, dependente apenas dos contratos
  públicos do core e sem integração inversa no runtime.
- Datasets versionados, casos e expectativas estáveis com preflight completo
  antes de consumir recursos produtivos.
- Observations imutáveis com política de captura segura e relatórios sem output
  final persistido por padrão.
- Registry local, métricas direcionais, scores finitos, findings e agregação
  determinística de resultados.
- Evaluators de correspondência exata, contenção, status, ferramentas, citações
  e guardrails, além da abstração provider-neutral de judge.
- Isolamento de erros de evaluator e executor, preservação de cancelamento e
  suporte explícito a suspensões HITL sem autoaprovação.

- Contratos provider-neutral de tracing e métricas, com implementações no-op e
  isolamento fail-open de adapters.
- Instrumentação do runtime para execução, modelos, ferramentas, aprovação,
  checkpoints, memória, knowledge e guardrails.
- Continuidade explícita de trace em `AgentContext` e checkpoints HITL, sem
  persistir adapters ou tokens de retomada.
- Allowlists de atributos, métricas de baixa cardinalidade e política de
  privacidade sem conteúdo ou exceptions cruas por padrão.

- Contratos provider-neutral de guardrails, registry e pipeline ordenado com
  transformações e rejeição fail-closed.
- Enforcement de entrada, model output, tool call, tool result e saída final,
  incluindo checkpoint, HITL e replay determinístico.
- Documentação da limitação de enforcement pós-acumulação no streaming.
- Fundação inicial do monorepo.
- Estrutura inicial do pacote core.
- Ferramentas de qualidade e integração contínua.
- Documentação inicial de arquitetura e contribuição.
- Contratos fundamentais e modelos imutáveis de agentes.
- Eventos mínimos e abstração assíncrona `Agent`.
- Máquina de estados do lifecycle de execução.
- Transições validadas e histórico ordenado de execução.
- Contratos expandidos de eventos de lifecycle.
- Factory de eventos com sequência monotônica por execução.
- Contratos provider-agnostic para capabilities e descriptors de modelos.
- Mensagens multimodais, requests e responses de modelos.
- Contratos de tool calls e structured output na fronteira do modelo.
- Contabilização de uso por chamada de modelo.
- Eventos estruturados para streaming de modelos.
- Interface `ModelProvider` e hierarquia abstrata de erros.
- Registry explícito de providers e catálogo imutável de modelos.
- Resolução de capabilities e restrições numéricas de modelos.
- Seleção determinística com strategy substituível e erros especializados.
- Estado de execução com mutações controladas e proteção após término.
- Snapshot imutável e conversão de estados terminais em `AgentResult`.
- Agregação de uso, contadores e journal validado de eventos por execução.
- Runtime provider-agnostic com loop multi-turn de modelo e ferramentas.
- Runtime streaming com eventos incrementais e resultado terminal discriminado.
- Acumulador determinístico para sequência, texto, tool calls e uso cumulativo.
- Fechamento cooperativo do stream em cancelamento ou interrupção do consumidor.
- Políticas imutáveis de limites estruturais, tokens, timeout e budget.
- Enforcement pós-resposta com precedência determinística e usage preservada.
- Deadline absoluto monotônico integrado a `run()` e `stream()`.
- Construção de requests com mensagens e attachments de imagem ou áudio.
- Normalização de erros de provider e preservação de cancelamento cooperativo.
- Fake provider reutilizável e testes end-to-end concorrentes.
- ADR de ownership exclusivo da execução pelo `AgentRuntime`.
- Organização dos testes por contexto arquitetural.
- Contratos provider-agnostic para definições, implementações e outputs de tools.
- Registry local com resolução exata e descoberta determinística de ferramentas.
- Fronteira segura de execução com requests e resultados estruturados.
- Avaliação explícita de permissões antes da validação de argumentos.
- Validação de argumentos pelo JSON Schema Draft 2020-12.
- Normalização de erros de tools e preservação do cancelamento cooperativo.
- Semântica declarativa de idempotência sem deduplicação fictícia.
- Allowlist ordenada de ferramentas por agente e requisito `TOOL_CALLING`.
- Journal de chamadas de ferramentas e deduplicação por execução.
- Mensagens de resultado de ferramenta seguras e determinísticas.
- Contratos imutáveis para solicitação, requisito e decisão de aprovação humana.
- Modos formais de aprovação em `ToolDefinition` e policy injetável.
- Suspensão retomável em `run()` e `stream()` sem espera bloqueante.
- Checkpoint versionado e serializável com storage abstrato e consumo atômico.
- Tokens opacos de uso único e validação explícita de decisões.
- Restauração de lifecycle, eventos, seleção, uso, contadores, limites e timeout.
- Retomada completa e incremental sem nova seleção ou mistura de transportes.
- Contratos imutáveis para tipos, escopos, registros, consultas e escritas de
  memória.
- `MemoryStore` assíncrono e `MemoryManager` com validação defensiva de escopo,
  tipo, duplicidade e expiração.
- Configuração explícita de memória por agente e resolução segura de escopos.
- Seleção determinística por quantidade e caracteres, sem truncamento ou LLM.
- Renderização de memória como contexto não autoritativo no prompt.
- Recuperação única compatível com multi-turn, streaming e retomada HITL.
- Policy explícita de escrita e integração do lifecycle `UPDATING_MEMORY`.
- Contratos provider-neutral para documentos, passagens, fontes, consultas,
  retrieval, contextos e citações de conhecimento externo.
- `KnowledgeManager` stateless com validação de fonte, duplicidade, limite e
  policy determinística por quantidade e caracteres.
- Opt-in por agente com allowlist ordenada de fontes e query builder extensível
  sem ampliação de acesso.
- Integração do lifecycle `RETRIEVING_KNOWLEDGE` antes da execução do modelo.
- Contexto de knowledge não autoritativo, recuperação única em multi-turn e
  streaming e preservação formal em checkpoints HITL.
- Extração final de marcadores válidos `K1`, `K2`… para `AgentResult.citations`.

### Alterado

- O estado genérico `WAITING` foi substituído por estados específicos de
  ferramenta e aprovação.
- O mapa do lifecycle passou a admitir os retornos normativos de ferramentas,
  aprovação e reparo de saída para `RUNNING`, além do processamento sequencial
  de ferramentas e da rejeição terminal de saída.
- `ExecutionLifecycle` agora sempre inicia em `CREATED`; restauração em outro
  estado fica reservada a um contrato futuro.
- `ModelStreamEvent` agora cria timestamp UTC quando ele não é fornecido.
- Identificadores de provider passam a remover somente whitespace externo,
  preservando capitalização e demais caracteres.
- Os testes normativos da abstração de modelos passaram a comprovar de forma
  explícita serialização, imutabilidade, streams completos e rejeição de JSON
  textual em argumentos de ferramentas.
- `Usage` passou a representar também tokens de cache de entrada e de
  raciocínio, preservando valores padrão compatíveis.
