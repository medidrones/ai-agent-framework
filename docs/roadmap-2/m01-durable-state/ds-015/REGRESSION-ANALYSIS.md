# Análise de regressão

As DS-004, DS-008, DS-009, DS-011, DS-012, DS-013 e DS-014 registraram
medições locais, porém não formam uma baseline diretamente comparável à matriz
DS-015: amostras, hardware, carga, instrumentação e duração diferem.

Portanto, a decisão honesta é:

```text
PERFORMANCE_BASELINE = ESTABLISHED
REGRESSION_COMPARISON = NOT_AVAILABLE
```

Os resultados DS-015 criam a primeira referência consolidada para comparação
futura. Essa condição não é descrita como “ausência de regressão histórica”.

O consolidador valida separadamente workloads isolados, faixa operacional de
1–250 workers, contenção, soak, segurança e o perfil extremo de 500 workers.
Uma saturação extrema permanece visível mesmo quando não bloqueia a faixa
operacional certificada.
