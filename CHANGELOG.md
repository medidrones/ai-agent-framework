# Registro de alterações

Todas as alterações relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [1.0.1] - 2026-09-15

### Alterado

- Promovidas as sete distribuições da candidata certificada `1.0.1rc1` para
  `1.0.1`, com versões e restrições internas sincronizadas em lockstep.
- Preservado o nome público `atlas-agent-framework` e o namespace Python
  `atlas_agent`, sem alteração funcional, de API pública ou dependência externa.

### Governança

- A tag `v1.0.0` permanece imutável. A versão `1.0.1` exige certificação dos
  próprios artefatos estáveis e autorização separada para publicação no PyPI.

## [1.0.1rc1] - 2026-09-14

### Alterado

- Iniciado o ciclo não destrutivo de promoção `1.0.1rc1 → 1.0.1`, preservando
  integralmente as tags e releases já publicadas.
- Versões e restrições internas das sete distribuições foram sincronizadas em
  lockstep, sem alteração funcional, de API, dependência ou contrato.

### Corrigido

- Os testes temporais de timeout em streaming e retomada HITL receberam margem
  suficiente para runners Windows sob carga, preservando as mesmas asserções e
  sem alterar o comportamento do runtime.

### Governança

- A candidata deriva do conteúdo técnico certificado do `1.0.0rc5`; novos
  artefatos e sign-offs foram exigidos antes da promoção estável.
- A certificação remota do `v1.0.1rc1` e os cinco owner sign-offs de Jorge
  Medina foram preservados em evidência versionada, resultando em
  `READY_FOR_STABLE` sem autorizar publicação no PyPI.

## [1.0.0rc5] - 2026-09-14

### Corrigido

- O montador do bundle de evidências passou a procurar o meta-package pelo nome
  normalizado `atlas_agent_framework`, correspondente à distribuição pública
  `atlas-agent-framework`.
- Adicionado teste de regressão que valida o inventário completo de wheels e
  sdists e impede o retorno acidental ao identificador ocupado `atlas_agent`.

### Governança

- A tag imutável `v1.0.0rc4` foi preservada após a falha restrita ao montador de
  evidências; a nova certificação será executada sobre `v1.0.0rc5`.
- A certificação remota do `v1.0.0rc5` e os cinco owner sign-offs de Jorge
  Medina foram preservados em evidência versionada, resultando em
  `READY_FOR_STABLE` sem autorizar publicação no PyPI.

## [1.0.0rc4] - 2026-09-14

### Corrigido

- O meta-package público foi renomeado de `atlas-agent` para
  `atlas-agent-framework` porque o nome anterior pertence a um projeto de
  terceiros no PyPI.
- Build, verificação de artefatos, instalação limpa, testes de empacotamento e
  documentação foram alinhados ao novo nome da distribuição.
- O namespace importável `atlas_agent` foi preservado; não há alteração na API
  Python nem no comportamento funcional.

### Segurança

- A validação de disponibilidade dos sete nomes de distribuição passou a fazer
  parte da certificação do RC antes de qualquer publicação no registry.

## [1.0.0] - 2026-09-14

### Alterado

- Promoção administrativa da candidata certificada `1.0.0rc3` para a versão
  estável `1.0.0`.
- Versões e restrições internas das sete distribuições sincronizadas em
  lockstep, sem alteração funcional, de API, dependência ou contrato.

### Segurança

- Preservados os cinco owner sign-offs, o digest do bundle certificado e a
  decisão `READY_FOR_STABLE` em documentação auditável.

## [1.0.0rc3] - 2026-09-14

### Corrigido

- O workflow de certificação agora substitui a referência leve criada pelo
  checkout do GitHub Actions pelo objeto anotado original da tag remota.
- A tag recuperada é validada como anotada e deve apontar exatamente para o
  mesmo `GITHUB_SHA` que disparou o workflow.

### Segurança

- As tags `v1.0.0rc1` e `v1.0.0rc2` permanecem imutáveis e não foram
  reutilizadas após suas respectivas falhas de certificação.

## [1.0.0rc2] - 2026-09-14

### Corrigido

- Preservação do espaço inicial do formato porcelain do Git ao separar
  alterações da fonte e evidências geradas durante a certificação.
- Diagnóstico do gate de limpeza passou a identificar explicitamente qualquer
  caminho inesperado.

### Segurança

- A tag `v1.0.0rc1` permaneceu imutável e não foi reutilizada após a falha do
  assembler.
- A certificação da `v1.0.0rc2` identificou que o checkout do GitHub Actions
  materializava a tag anotada como uma referência leve no runner.

## [1.0.0rc1] - 2026-09-13

### Adicionado

- Auditoria do grafo de dependências, ciclos, API pública e segredos em
  artefatos.
- Stress com 100 execuções concorrentes e baseline de performance offline.
- Modelo de ameaças, checklist de produção, prontidão, SBOM CycloneDX e
  checksums SHA-256.
- Matriz bloqueante Python 3.12/3.13 em Linux/Windows e workflow de candidata
  sem publicação automática.

### Alterado

- Versão lockstep das sete distribuições promovida para `1.0.0rc1`.
- CI passou a arquivar JUnit, coverage, auditorias e bundle da candidata.

### Segurança

- Formalizadas fronteiras de confiança, riscos residuais e exigências do host
  para identidade, TLS, egress, plugins, MCP, retenção e idempotência.

### Adicionado

- Estratégia oficial de sete distribuições modulares, incluindo o meta-package
  opcional `atlas-agent` e extras `openai`, `rest`, `grpc`, `config`,
  `evaluation`, `mcp` e `full`.
- Fonte única `VERSION`, geração sincronizada de versões PEP 440 e política de
  releases lockstep orientada por SemVer.
- Inspeção automatizada de wheels/sdists, smoke tests em ambientes isolados,
  verificação de namespace, `py.typed`, licenças e entry points.
- Documentação de instalação, pacotes, compatibilidade, depreciação, API pública
  e processo de release.

### Alterado

- OpenAI, FastAPI e gRPC passaram a dependências opcionais de seus respectivos
  extras; o core deixou de declarar PyYAML e o pacote config deixou de exigir
  adapters externos.
- Sdists passaram a excluir testes e incluir README e licença de cada
  distribuição.

- Distribuição opcional `atlas-agent-config` com schema v1 fechado, modelos
  Pydantic, loaders seguros para YAML/JSON e overrides determinísticos.
- Registry local de factories tipadas e composition root assíncrona para
  providers, ferramentas, memória, knowledge, guardrails, observabilidade, MCP
  e adapters, com preflight, rollback e ownership explícito.
- Referências e resolução injetada de segredos, fingerprint canônico, ativação
  explícita de plugins e defaults seguros sem importação ou inicialização
  implícita de integrações.
- JSON Schema, exemplos e documentação em português para composição,
  segurança, factories, segredos e overrides.

- Distribuição opcional `atlas-agent-adapters` com fachada provider-neutral de
  execução, registro explícito de agentes, identidade confiável, autorização,
  limites de servidor e idempotência abstrata.
- API REST/FastAPI v1 com execução, retomada, SSE, health e readiness, sem
  servidor global ou lifecycle implícito.
- Serviço gRPC `atlas.agent.v1` com operações unary e server streaming,
  deadline propagado e contratos protobuf versionados e gerados no repositório.
- Consumer e publisher broker-neutral com envelopes versionados, correlação,
  causação, semântica explícita de ack/retry e publicação terminal por padrão.
- Testes de contrato, integração local, fluxos negativos, segurança e cobertura
  isolada dos adapters, além da documentação de implantação e versionamento.

- Distribuição opcional `atlas-agent-mcp`, dependente apenas dos contratos
  públicos do core e do SDK oficial do Model Context Protocol.
- Cliente MCP assíncrono com lifecycle explícito, negociação pelo SDK,
  descoberta de ferramentas, recursos, templates e prompts e limites de
  resposta.
- Transportes stdio e Streamable HTTP sem execução de shell, com ownership
  explícito de clientes e proteção de credenciais em configuração e erros.
- Importação de ferramentas remotas por allowlist, nomes locais determinísticos,
  preflight de colisões e rollback em ordem inversa.
- Servidor MCP do Atlas com exposição explícita e execução de ferramentas pelo
  `ToolExecutor`, preservando as políticas do runtime.
- Testes de integração locais para stdio e Streamable HTTP, fluxos de segurança,
  HITL, guardrails, limites, deduplicação, concorrência e cancelamento.
- Documentação de cliente, servidor, ferramentas, recursos, prompts,
  transportes, segurança e arquitetura MCP.

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
