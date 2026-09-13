# Arquitetura dos adapters externos

A distribuição `atlas-agent-adapters` é uma camada externa e opcional. Ela
depende apenas das APIs públicas do core e das bibliotecas de transporte. Não há
import inverso em `atlas-agent-core`.

```text
FastAPI ─┐
gRPC    ─┼─ DTOs de wire ─ AgentExecutionService ─ contratos do core
Broker  ─┘                       │
                    registry + policies + idempotência
```

DTOs de wire não são modelos do core. A tradução explícita evita expor objetos
de provider ou aceitar autoridade dentro do payload. A fachada compartilhada
mantém as mesmas regras de autorização, limites e mapeamento de resultados em
todos os transportes.

Lifecycle de processo permanece no composition root: FastAPI é criada, mas não
servida; o servicer gRPC é registrado, mas não abre listener; o consumer recebe
entregas, mas não conecta ao broker. Configuração chega por construtor e nenhum
módulo lê ambiente ou cria singleton.

Adapters podem ser montados por factories próprias da aplicação ou por plugins
confiáveis, mas a Task 021 não amplia a API de plugins com um tipo genérico de
adapter. Isso evita forçar lifecycle e configuração de transportes distintos em
um contrato artificial. A composição explícita continua sendo a integração
recomendada.

Idempotência é uma porta da camada de aplicação. A implementação em memória é
apenas local; garantias distribuídas dependem do adapter persistente e da
infraestrutura. Da mesma forma, autenticação e autorização de transporte não
são implementadas pelo core.
