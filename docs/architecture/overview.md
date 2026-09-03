# Visão geral da arquitetura

O Atlas Agent Framework é um SDK Python modular cujo centro estável é um core
pequeno e neutro de provedor. Os consumidores podem usar esse core diretamente
ou adicionar plugins e adapters de transporte opcionais.

## Propósito e escopo

O framework fornece abstrações reutilizáveis para agentes de IA sem incorporar
uma aplicação de negócio. Nesta fase, o escopo inclui a fundação do monorepo,
os gates de qualidade, os contratos fundamentais de agentes e o protocolo de
lifecycle, além da abstração provider-agnostic de modelos. O runtime coordena
chamadas completas ou incrementais e executa ciclos multi-turn com ferramentas
permitidas pelo agente. Integrações concretas continuam em pacotes externos.

## Direção das dependências

```text
Consumidores
    |
Adapters e plugins
    |
Contratos do core
```

As dependências do código-fonte apontam para o core. O core não sabe qual
provedor de modelo, banco de dados, broker, banco vetorial ou transporte
implementará seus contratos.

## Organização do repositório

- `packages/atlas-agent-core` contém o pacote importável `atlas_agents`.
- Pacotes futuros conterão implementações de provedores e infraestrutura.
- `docs` registra restrições e decisões arquiteturais.
- `examples` demonstrará integrações sem introduzir lógica de negócio no
  framework.

## Responsabilidades iniciais

- manter o pacote core instalável e tipado;
- definir modelos imutáveis para dados de entrada e saída;
- oferecer uma abstração assíncrona para agentes concretos;
- validar transições por uma máquina de estados declarativa;
- registrar histórico e representar eventos sem acoplamento a um event bus;
- definir requests, responses e streaming de modelos sem SDK concreto;
- permitir providers substituíveis por uma interface async-first;
- registrar providers explicitamente e selecionar modelos deterministicamente;
- garantir execuções locais e no CI a partir da raiz;
- documentar limites antes de adicionar integrações;
- impedir dependências concretas dentro do core;
- controlar o estado local de uma execução sem executar providers ou
  ferramentas;
- executar múltiplos turns por `ModelProvider.generate()` ou exclusivamente
  por `ModelProvider.stream()` no modo incremental, sem SDK concreto;
- validar e reconstruir streams estruturados sem expor chunks de SDKs.
- aplicar limites e budget por execução com checker puro e deadline monotônico.
- registrar ferramentas em ordem determinística e derivar sua visão do modelo;
- autorizar, validar e executar ferramentas conhecidas por uma fronteira segura.

## Extensibilidade e evolução

A evolução ocorre por contratos no core e implementações em pacotes opcionais.
Novos providers, stores ou transportes devem poder ser instalados e substituídos
sem alterar o modelo público do core. Dependências de infraestrutura ficam
isoladas na distribuição que as utiliza.

`ExecutionState` permanece responsável somente por mutações controladas,
snapshots e resultados terminais. `AgentRuntime` possui ownership único da
orquestração e realiza quantas chamadas async a `ModelProvider.generate()` ou
`ModelProvider.stream()` forem admitidas pelos limites do loop. O runtime
integra tools do core sem conhecer suas dependências concretas. Nenhum provider
concreto, retry, fallback ou reconexão é implementado no core.

As políticas são value objects imutáveis fornecidos ao runtime. O checker não
conhece lifecycle ou provider; ele retorna violações estruturadas. O runtime
aplica pre-check antes da invocação, pós-check após usage e converte a decisão
nos estados terminais já definidos, sem alterar o mapa de transições.

Ferramentas recebem dependências diretamente em seus construtores. O contexto
restrito não oferece container de serviços. O executor resolve somente nomes
exatos já registrados, verifica autorização antes do schema e não importa ou
executa código indicado pelo modelo. Consulte
[`docs/reference/tools.md`](../reference/tools.md).

O agente restringe quais registros podem ser apresentados e executados. O
estado guarda o histórico de mensagens e um journal imutável de tool calls para
reutilização segura dentro da execução. Consulte
[`docs/reference/multi-turn-runtime.md`](../reference/multi-turn-runtime.md).
