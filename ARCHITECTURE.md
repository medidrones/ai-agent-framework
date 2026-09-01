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
toda alteração passa por um mapa declarativo, produz uma
`ExecutionTransition` imutável e entra no histórico ordenado. Estados terminais
são centralizados e não possuem transições de saída. Toda instância nova inicia
em `CREATED`; restauração futura exigirá um contrato explícito.

O lifecycle não conhece event bus ou observabilidade. `AgentEventFactory`
transforma transições em eventos separadamente, mantendo sequência local por
execução. Essa separação evita acoplar regras de estado ao transporte futuro de
eventos.

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
pacote `atlas-agent-core`: definição, entrada, contexto, identidade, resultado,
uso, erro estruturado, lifecycle, transições, eventos e a abstração `Agent`.

Esses tipos representam snapshots imutáveis nas fronteiras do framework. IDs
são strings opacas e não impõem UUID. Metadados são explicitamente tipados,
isolados por instância e validados como serializáveis em JSON. Eventos exigem
timestamps com fuso horário.

Runtime, providers, ferramentas e armazenamento serão introduzidos
incrementalmente em tarefas posteriores. O lifecycle atual formaliza estados,
mas não executa modelos nem fornece um loop de execução.

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
