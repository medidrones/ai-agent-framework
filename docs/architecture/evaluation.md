# Arquitetura de avaliação

## Separação produtiva

```text
                 Produção
                    │
                    ▼
               AgentRuntime
                    │
                    ▼
                AgentResult
                    │
       ┌────────────┴────────────┐
       │                         │
       ▼                         ▼
  Consumidor                 Evaluation
                                  │
                                  ▼
                          EvaluationReport
```

Evaluation observa contratos públicos e nunca devolve decisões ao runtime. Não
há `evaluation_mode`, retry, troca de modelo, mudança de prompt, autoaprovação,
mock automático, transformação de output ou alteração de guardrails e memória.

```text
EvaluationDataset
      │
      ▼
EvaluationRunner ──────────> EvaluatorRegistry
      │                            │
      ▼                            ▼
EvaluationExecutor             Evaluators
      │                            │
      ▼                            │
AgentRuntime → AgentResult         │
      │                            │
      ▼                            │
EvaluationObservation ─────────────┘
      │
      ▼
EvaluationResults → EvaluationReport
```

## Direção de dependência

`atlas-agent-evaluation` é uma distribuição opcional que depende de
`atlas-agent-core`. O namespace `atlas_agents` é extensível somente para permitir
subpacotes distribuídos separadamente. O código do core não importa
`atlas_agents.evaluation`.

## Responsabilidades

| Responsabilidade | Runtime | Evaluation |
| --- | ---: | ---: |
| executar modelos e ferramentas | sim | não diretamente |
| aplicar guardrails | sim | apenas observar |
| atualizar memória | sim | não |
| produzir `AgentResult` | sim | não |
| comparar expectativa | não | sim |
| produzir scores e findings | não | sim |
| mutar `AgentResult` | não | nunca |

O adapter de runtime recebe instâncias explicitamente configuradas. Avaliações
que possam causar efeitos externos devem usar stores isolados, ferramentas fake,
sandbox ou staging, credenciais de teste e dados não produtivos. O framework não
desabilita efeitos de forma oculta, pois isso criaria um caminho diferente do
usado em produção.

## Determinismo e isolamento

Preflight percorre todo o dataset antes de chamar o executor. Casos e
expectativas são processados sequencialmente nas ordens declaradas. Registry,
clock e ID factory pertencem à instância do runner; não há estado global ou
service locator. Output de modelos externos pode continuar não determinístico,
mas a orquestração sobre as mesmas observations mantém ordem estável.
