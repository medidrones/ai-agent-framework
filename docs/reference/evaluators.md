# Evaluators

O pacote inclui evaluators determinísticos para invariantes estruturais:

| Evaluator | ID padrão | O que mede |
| --- | --- | --- |
| `ExactMatchEvaluator` | `exact-output` | igualdade textual literal |
| `ContainsEvaluator` | `contains` | presença de fragmento literal |
| `ExecutionStatusEvaluator` | `status` | status público do runtime |
| `ToolUsageEvaluator` | `tool-usage` | ferramentas realmente executadas |
| `CitationEvaluator` | `citation-validity` | quantidade e IDs de citações |
| `GuardrailOutcomeEvaluator` | `guardrail-outcome` | estágio, decisão e código seguro |

Replays deduplicados não contam como novas execuções de ferramenta.
`CitationEvaluator` valida estrutura, não verdade factual nem groundedness.
`GuardrailOutcomeEvaluator` usa `GuardrailRecord` e não precisa do conteúdo
avaliado.

## Métricas e scores

`EvaluationMetric` define ID, descrição, direção e limites opcionais. Valores,
thresholds e limites devem ser finitos.

| Direção | Regra automática |
| --- | --- |
| `HIGHER_IS_BETTER` | `value >= threshold` |
| `LOWER_IS_BETTER` | `value <= threshold` |
| `NONE` | nenhuma decisão automática |

Métricas com o mesmo ID precisam ter definições idênticas. Definições
incompatíveis geram `IncompatibleEvaluationMetricError` e não são agregadas.

## Judge provider-neutral

`EvaluationJudge`, `JudgeRequest` e `JudgeResponse` formam uma fronteira opt-in
sem SDK de fornecedor. `JudgeEvaluator` recebe o judge no construtor; o pacote
não seleciona modelos nem implementa um segundo runtime.

Candidate, reference, rubric e reason são dados não confiáveis. O score do judge
não é verdade objetiva, e adapters futuros devem tratar prompt injection,
redação e isolamento. Para invariantes verificáveis, prefira evaluators
determinísticos.
