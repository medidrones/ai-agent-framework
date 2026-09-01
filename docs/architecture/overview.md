# Visão geral da arquitetura

O Atlas Agent Framework é um SDK Python modular cujo centro estável é um core
pequeno e neutro de provedor. Os consumidores podem usar esse core diretamente
ou adicionar plugins e adapters de transporte opcionais.

## Propósito e escopo

O framework fornece abstrações reutilizáveis para agentes de IA sem incorporar
uma aplicação de negócio. Nesta fase, o escopo inclui a fundação do monorepo,
os gates de qualidade e os contratos fundamentais de agentes. Comportamento de
runtime, integrações e lifecycle pertencem às próximas fases.

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
- representar eventos mínimos sem implementar uma máquina de estados;
- garantir execuções locais e no CI a partir da raiz;
- documentar limites antes de adicionar integrações;
- impedir dependências concretas dentro do core.

## Extensibilidade e evolução

A evolução ocorre por contratos no core e implementações em pacotes opcionais.
Novos providers, stores ou transportes devem poder ser instalados e substituídos
sem alterar o modelo público do core. Dependências de infraestrutura ficam
isoladas na distribuição que as utiliza.

O core intencionalmente não contém lógica de runtime. Os contratos atuais
permitem implementar agentes concretos, mas não coordenam sua execução.
Comportamentos serão adicionados em fases pequenas e revisáveis de forma
independente.
