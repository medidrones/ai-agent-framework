# Stress de concorrência

A certificação executa ciclos mixed independentes com 1, 10, 50, 100, 250 e
500 workers. O perfil 500 identifica saturação e não constitui promessa de
capacidade.

Também são executadas disputas sobre uma única identidade com 100 e 500
participantes:

| Operação | Invariante |
| --- | --- |
| consumo atômico | um vencedor e `N-1` rejeições |
| optimistic update | um writer e `N-1` conflitos de revisão |
| lease acquire | um owner e `N-1` conflitos de ownership |

O throughput de contenção considera as `N` tentativas. A latência do único
vencedor é preservada separadamente para que os relatórios não apresentem uma
distribuição estatística artificial.

Lost update, consumo duplicado ou mais de um owner reprovam o cenário,
independentemente da latência observada.
