# Contratos de orquestração

| Contrato | Responsabilidade |
| --- | --- |
| `WorkflowDefinition` | descrição declarativa e versionada |
| `WorkflowNode` | unidade lógica sem comportamento de execução |
| `WorkflowEdge` | conexão dirigida com condição simbólica opcional |
| `WorkflowInput` | entrada JSON e correlação |
| `WorkflowContext` | fatos serializáveis da instância |
| `WorkflowResult` | snapshot explícito ou resultado terminal |
| `WorkflowEvent` | fato funcional versionado |
| `WorkflowOrchestrator` | fronteira assíncrona de coordenação futura |

As políticas públicas cobrem routing, concorrência, falha, retry, deadline,
budget e autorização. Elas não possuem algoritmos ou implementações padrão.
