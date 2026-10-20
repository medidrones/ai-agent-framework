# API pública da OR-001

Os contratos são importáveis de `atlas_agents.orchestration` e, por
conveniência compatível com a API atual, de `atlas_agents`.

```python
from atlas_agents import WorkflowDefinition, WorkflowNode, WorkflowNodeKind

workflow = WorkflowDefinition(
    workflow_id="support.triage",
    version="1.0.0",
    name="Triagem",
    nodes=(
        WorkflowNode(
            node_id="triage",
            kind=WorkflowNodeKind.AGENT,
            agent_ref="support-agent",
        ),
    ),
)
```

Construir uma definição não a executa. O protocolo `WorkflowOrchestrator` não
possui implementação concreta na OR-001.
