# Registro de alterações

Todas as alterações relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

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
