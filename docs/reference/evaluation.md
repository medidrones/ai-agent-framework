# Framework de avaliação

O pacote `atlas-agent-evaluation` mede a qualidade de resultados sem alterar o
runtime produtivo. Ele depende dos contratos públicos de `atlas-agent-core`; o
core não importa evaluation.

```text
atlas-agent-evaluation
        ↓
atlas-agent-core
```

## Execução básica

```python
from atlas_agents.evaluation import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationExpectation,
    EvaluationObservation,
    EvaluationRunner,
    EvaluatorRegistry,
    ExactMatchEvaluator,
)

registry = EvaluatorRegistry((ExactMatchEvaluator(),))
runner = EvaluationRunner(registry=registry)

case = EvaluationCase(
    case_id="saudacao-pt-br",
    name="Saudação em português",
    expectations=(
        EvaluationExpectation(
            expectation_id="saida-exata",
            evaluator_id="exact-output",
            expected="Olá!",
        ),
    ),
)
dataset = EvaluationDataset(
    dataset_id="smoke",
    name="Smoke tests",
    version="1.0",
    cases=(case,),
)
observation = EvaluationObservation(
    execution_id="execucao-isolada",
    agent_id="assistente",
    status="completed",
    output="Olá!",
)

report = await runner.evaluate_dataset(
    dataset=dataset,
    observations={case.case_id: observation},
)
```

O runner também aceita um `EvaluationExecutor`. O adapter
`AgentRuntimeEvaluationExecutor` usa `AgentRuntime.run()` sem flags ou caminhos
especiais. Cada contexto e `execution_id` são fornecidos por uma factory do
consumidor; `case_id` não é reutilizado automaticamente.

## Contrato do evaluator

```python
async def evaluate(
    self,
    case: EvaluationCase,
    expectation: EvaluationExpectation,
    observation: EvaluationObservation,
    context: EvaluationContext,
) -> EvaluationResult: ...
```

Evaluators recebem somente modelos imutáveis. Dependências externas entram no
construtor. O registry é local, mantém ordem de registro e rejeita IDs
duplicados. Antes de qualquer execução, o preflight valida todos os evaluator
IDs e definições de métricas.

## Semântica de erro

| Situação | Comportamento |
| --- | --- |
| dataset inválido | aborta antes da execução |
| evaluator ausente | aborta no preflight |
| exception do evaluator | resultado `ERROR`, sem score, continua |
| falha do judge | resultado `ERROR`, sem score, continua |
| exception do executor | caso `ERROR`, continua |
| runtime retorna `FAILED` ou `REJECTED` | observation válida |
| runtime suspende para HITL | observation válida, sem autoaprovação |
| cancelamento | `CancelledError` é repropagada |

Exceptions e stack traces não entram no relatório. Falha operacional nunca é
convertida em score zero.

## Outcomes

| Condição | Outcome do caso |
| --- | --- |
| erro do executor ou evaluator | `ERROR` |
| algum score falha, sem erros | `FAILED` |
| todos os scores decisórios passam | `PASSED` |
| nenhum score possui decisão | `UNSCORED` |

O relatório aplica prioridade `ERROR`, `FAILED`, `PASSED`, `UNSCORED`. Seu
summary contém contagens exclusivas, erros operacionais e agregados por métrica
com `mean`, `min`, `max`, aprovados, reprovados e não pontuados. Dataset vazio
gera relatório válido `UNSCORED`, sem inventar médias iguais a zero.

## Privacidade

`EvaluationObservation` disponibiliza a saída final ao evaluator durante a
medição, mas `EvaluationCaseResult` persiste apenas
`EvaluationObservationSummary`. Por padrão:

- conteúdo intermediário de modelo não é capturado;
- argumentos e outputs de ferramentas não são capturados;
- conteúdo de memória e passagens de knowledge não são capturados;
- mensagens completas de erro, credenciais e tokens de retomada nunca entram;
- nomes/status de ferramentas, citações e registros seguros de guardrails podem
  ser avaliados.

`EvaluationCapturePolicy` permite opt-in explícito de argumentos, outputs e
eventos intermediários. Quem habilitar esses campos assume a classificação,
redação, retenção e proteção dos dados resultantes.

## Limitações atuais

O runner é sequencial para preservar ordem e evitar complexidade de rate limit.
Não há loader YAML/JSON, storage de datasets, dashboard, experiment tracker,
comparador de regressão ou gate de CI. Esses recursos podem consumir o relatório
serializável externamente.

## Matriz de conformidade

| Área | Status | Evidência principal |
| --- | --- | --- |
| distribuição independente | PASS | `test_architecture.py` |
| independência do core | PASS | architecture import guard |
| `EvaluationCase` e expectation | PASS | `test_contracts.py` |
| IDs estáveis e duplicidade | PASS | `test_contracts.py` |
| dataset versionado e ordenado | PASS | `test_contracts.py` |
| dataset vazio | PASS | `test_runner.py` |
| preflight antes do executor | PASS | `test_runner.py` |
| observation imutável | PASS | `test_contracts.py` |
| captura segura por padrão | PASS | `test_contracts.py` |
| captura rica por opt-in | PASS | `test_contracts.py` |
| contrato async de evaluator | PASS | `evaluator.py` e mypy |
| registry local e ordenado | PASS | `test_contracts.py` |
| proteção de evaluator duplicado | PASS | `test_contracts.py` |
| evaluator ausente | PASS | `test_runner.py` |
| métrica e direção | PASS | `test_contracts.py` |
| bounds e threshold | PASS | `test_contracts.py` |
| proteção contra NaN/infinito | PASS | `test_contracts.py` |
| resultados e findings | PASS | `test_contracts.py` |
| erro sem score falso | PASS | `test_runner.py` |
| runner sequencial | PASS | `test_runner.py` |
| ordenação determinística | PASS | `test_runner.py` |
| exact match | PASS | `test_evaluators.py` |
| contains | PASS | `test_evaluators.py` |
| status produtivo | PASS | `test_evaluators.py` |
| uso real de tools | PASS | `test_evaluators.py` |
| citações estruturais | PASS | `test_evaluators.py` |
| outcomes de guardrail | PASS | `test_evaluators.py` |
| abstração de judge | PASS | `test_evaluators.py` |
| ausência de SDK de judge | PASS | `test_architecture.py` |
| isolamento de erro do evaluator | PASS | `test_runner.py` |
| isolamento de erro do executor | PASS | `test_runner.py` |
| propagação de cancelamento | PASS | `test_runner.py` |
| imutabilidade do resultado | PASS | `test_runner.py` |
| ausência de mutação do runtime | PASS | `test_runtime_executor.py` |
| suspensão HITL sem autoaprovação | PASS | `test_runtime_executor.py` |
| relatório privacy-safe | PASS | `test_contracts.py` e `test_runner.py` |
| agregação de summary | PASS | `test_runner.py` |
| métricas incompatíveis | PASS | `test_runner.py` |
| ausência de service locator | PASS | revisão arquitetural e Ruff |
| ausência de infraestrutura | PASS | `test_architecture.py` |
| tipagem estática | PASS | mypy, 223 arquivos |
| cobertura de evaluation | PASS | pytest-cov, acima de 90% |
| suíte completa | PASS | 800 testes |
| build do core | PASS | `uv build --package atlas-agent-core` |
| build de evaluation | PASS | `uv build --package atlas-agent-evaluation` |
