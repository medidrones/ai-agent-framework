# Arquitetura da configuração declarativa

`atlas-agent-config` é uma composition root opcional. Ele depende de contratos
públicos do core e dos adapters externos, enquanto o core não conhece o pacote
de configuração.

```text
YAML / JSON / objeto Python
          ↓
 AtlasConfig + validação de referências
          ↓
 ConfigurationFactoryRegistry ← factories explícitas do host
          ↓
 AtlasCompositionBuilder
          ↓
 registries + AgentRuntime + integrações opcionais
```

O registro de factories descreve construção, não descoberta. Provider OpenAI,
clientes MCP, bancos e transportes continuam em pacotes próprios. Isso preserva
inversão de dependência e mantém a composição Python manual disponível.

A configuração não é estado de execução. Ela não contém clientes, locks,
credenciais resolvidas, sessões ou checkpoints. A composição detém somente os
recursos declarados pelas factories e os libera em ordem inversa; colaboradores
injetados são de propriedade do chamador.
