# Fronteira do orquestrador

`WorkflowOrchestrator.execute()` é um protocolo assíncrono que recebe definição,
entrada e contexto, retornando `WorkflowResult`. A interface não recebe
clientes de infraestrutura nem consulta registries globais.

Não foi criado contrato de streaming: não há semântica de execução consolidada
que justifique fixar essa API na OR-001. `AgentRuntime` continua dono exclusivo
da execução individual e não ganhou dependência do orquestrador.
