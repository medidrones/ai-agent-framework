# Guardrails

Guardrails são políticas de governança provider-neutral avaliadas em pontos
precisos do runtime. O agente opta explicitamente por IDs registrados em
`AgentGuardrailConfig`; registrar uma implementação não a habilita
automaticamente.

## Contratos

`GuardrailStage` define `INPUT`, `MODEL_OUTPUT`, `TOOL_CALL`, `TOOL_RESULT` e
`FINAL_OUTPUT`. Cada `Guardrail` possui ID e estágio fixos e implementa
`evaluate()` de forma assíncrona. O resultado declara `ALLOW`, `TRANSFORM` ou
`REJECT`; rejeições também informam enforcement `OPERATION` ou `EXECUTION`.

`GuardrailPipeline` preserva a ordem configurada, encadeia transformações e
interrompe no primeiro `REJECT`. Exceções nunca significam permissão implícita:
o runtime falha fechado com `guardrail_evaluation_failed`.

```python
config = AgentGuardrailConfig(
    input_guardrails=("input-size", "input-redaction"),
    tool_call_guardrails=("tool-policy",),
    final_output_guardrails=("output-redaction",),
)
```

## Valores por estágio

- `InputGuardrailInput`: definição declarativa e `AgentInput` imutáveis;
- `ModelOutputGuardrailInput`: resposta completa e número do turno;
- `ToolCallGuardrailInput`: chamada resolvida e definição da ferramenta;
- `ToolResultGuardrailInput`: chamada e resultado Atlas normalizado;
- `FinalOutputGuardrailInput`: candidato estruturalmente válido.

Transformações de entrada preservam `ExecutionState.input_data` e produzem
`effective_input`. Memory, Knowledge e o modelo recebem somente a versão
efetiva. Transformações de model output podem alterar conteúdo, mas não tool
calls, usage, finish reason, identidade ou metadados da resposta.

Transformações de tool call só podem alterar argumentos. O runtime revalida o
schema antes de aprovação, contagem e execução. Transformações de tool result
ocorrem antes da mensagem `TOOL`. O registro preserva o resultado Atlas
normalizado e sua versão efetiva.

## Privacidade e auditoria

`GuardrailRecord` e eventos guardam somente estágio, ID, decisão, códigos de
violação e tipos de transformação. Entrada, saída, argumentos e resultados não
são registrados nesses payloads. O contexto não expõe estado mutável, serviços
ou credenciais.

O core não fornece moderação, detecção de PII ou prompt injection. Integrações
com serviços de políticas pertencem a adapters opcionais e recebem suas
dependências por construtor.

## Códigos estáveis

- `guardrail_manager_required`;
- `guardrail_not_registered`;
- `guardrail_stage_mismatch`;
- `guardrail_evaluation_failed`;
- `guardrail_protocol_violation`;
- `guardrail_invalid_transformation`;
- códigos de rejeição específicos de cada estágio.
