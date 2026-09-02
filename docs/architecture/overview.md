# Visão geral da arquitetura

O Atlas Agent Framework é um SDK Python modular cujo centro estável é um core
pequeno e neutro de provedor. Os consumidores podem usar esse core diretamente
ou adicionar plugins e adapters de transporte opcionais.

## Propósito e escopo

O framework fornece abstrações reutilizáveis para agentes de IA sem incorporar
uma aplicação de negócio. Nesta fase, o escopo inclui a fundação do monorepo,
os gates de qualidade, os contratos fundamentais de agentes e o protocolo de
lifecycle, além da abstração provider-agnostic de modelos. O runtime single-turn
já coordena uma chamada completa ou incremental pela abstração de modelos;
integrações concretas e comportamentos multi-turn pertencem às próximas fases.

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
- executar um único turn por `ModelProvider.generate()` ou
  `ModelProvider.stream()`, sem SDK concreto;
- validar e reconstruir streams estruturados sem expor chunks de SDKs.

## Extensibilidade e evolução

A evolução ocorre por contratos no core e implementações em pacotes opcionais.
Novos providers, stores ou transportes devem poder ser instalados e substituídos
sem alterar o modelo público do core. Dependências de infraestrutura ficam
isoladas na distribuição que as utiliza.

`ExecutionState` permanece responsável somente por mutações controladas,
snapshots e resultados terminais. `AgentRuntime` possui ownership único da
orquestração e realiza uma chamada async a `ModelProvider.generate()` ou
`ModelProvider.stream()`. Nenhum provider concreto, tool, retry, fallback,
reconexão ou segundo turno é implementado no core.
