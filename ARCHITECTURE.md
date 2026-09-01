# Arquitetura

O Atlas Agent Framework é organizado como um monorepo Python. Sua arquitetura
se baseia em inversão de dependência: contratos estáveis do core são
implementados por pacotes opcionais de infraestrutura.

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

## Escopo atual

Atualmente, o repositório inclui apenas o workspace e a estrutura inicial do
pacote `atlas-agent-core`. Runtime, provedores, ferramentas e armazenamento
serão introduzidos incrementalmente depois que seus contratos forem definidos.

Os limites detalhados dos pacotes estão documentados em
[`docs/architecture/dependency-rules.md`](docs/architecture/dependency-rules.md).
