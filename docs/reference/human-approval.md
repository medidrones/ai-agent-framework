# Aprovação humana

O Human-in-the-Loop (HITL) do Atlas permite interromper uma execução antes de
uma ferramenta sensível, persistir seu estado e retomá-la após uma decisão
externa. O core não apresenta interface, não consulta banco de dados e não
mantém uma coroutine esperando a pessoa aprovadora.

## Contratos

- `ApprovalRequest` descreve a solicitação e contém apenas um resumo seguro da
  ação. Para ferramentas, `ToolApprovalSubject` expõe ID, nome e nomes das
  chaves dos argumentos, nunca os valores completos.
- `ApprovalDecision` registra `APPROVE` ou `REJECT`, instante, identidade
  opcional, motivo e metadados serializáveis.
- `ApprovalRequirement` é a união discriminada entre `ApprovalNotRequired` e
  `ApprovalRequired`.
- `ApprovalPolicy` avalia localmente ferramentas em modo
  `POLICY_CONTROLLED`. A implementação padrão `NoApprovalPolicy` não exige
  aprovação.
- `ApprovalDecisionValidator` valida a correspondência entre solicitação e
  decisão. A implementação padrão exige o mesmo `approval_request_id`.

`ToolDefinition.approval_mode` declara a política básica:

| Modo | Consulta a policy | Resultado |
| --- | --- | --- |
| `NOT_REQUIRED` | não | execução direta |
| `REQUIRED` | não | aprovação obrigatória |
| `POLICY_CONTROLLED` | sim | resultado da `ApprovalPolicy` |

Esse campo não é enviado ao modelo em `ModelToolDefinition`.

## Pipeline normativo

```text
allowlist do agente
  → resolução da ferramenta
  → permissão
  → validação dos argumentos
  → avaliação de aprovação
  → limite de ferramentas
  → incremento do contador
  → execução
```

Uma solicitação inválida ou sem permissão não revela nem cria aprovação. Uma
ferramenta suspensa ainda não foi executada e não incrementa
`tool_call_count`.

## Suspensão e decisão

Quando a aprovação é necessária, o runtime registra `APPROVAL_REQUESTED`,
transiciona de `WAITING_FOR_TOOL` para `WAITING_FOR_APPROVAL`, salva um
`ExecutionCheckpoint` e registra `EXECUTION_SUSPENDED`. A chamada retorna
`ExecutionSuspension`, que não é um `AgentResult` e não representa término do
lifecycle.

```python
outcome = await runtime.run(
    agent=agent,
    input_data=agent_input,
    context=context,
)

if isinstance(outcome, ExecutionSuspension):
    decision = ApprovalDecision(
        approval_request_id=outcome.approval_request.approval_request_id,
        decision=ApprovalDecisionType.APPROVE,
        decided_at=datetime.now(UTC),
    )
    outcome = await runtime.resume(
        resume_token=outcome.resume_token,
        decision=decision,
    )
```

Uma aprovação válida registra `EXECUTION_RESUMED` e `APPROVAL_GRANTED`, executa
a chamada original e continua no mesmo provider e modelo. Rejeição ou expiração
produz `AgentResult` terminal com status `REJECTED`; a ferramenta não é
executada.

Várias ferramentas sensíveis no mesmo batch são aprovadas sequencialmente.
Cada suspensão recebe uma solicitação e um token novos.

## Streaming

`stream()` termina a invocação suspensa com um `RuntimeSuspensionItem`, sem
emitir `RuntimeResultItem`. `resume_stream()` continua exclusivamente por
`ModelProvider.stream()` e preserva a sequência dos eventos. Um checkpoint de
`stream()` não pode ser retomado por `resume()`, nem o inverso.

## Segurança

- o token de retomada é aleatório, opaco e diferente dos IDs de execução e de
  aprovação;
- o token não aparece em eventos;
- argumentos completos não entram no pedido de aprovação;
- o runtime não aprova automaticamente;
- o core não contém UI, prompt de console, storage concreto ou workflow engine;
- metadados e checkpoints devem permanecer livres de credenciais e segredos.

Consulte [checkpoint e retomada](checkpoint-resume.md) para persistência,
consumo atômico e reconstrução do estado.
