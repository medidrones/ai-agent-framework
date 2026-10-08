# Corrida entre atualização e consumo

`compare_and_swap()` e `consume()` operam sobre a mesma linha e são
serializados pelo PostgreSQL.

| Operação que obtém o lock primeiro | Resultado do CAS | Resultado do consumo | Estado final |
| --- | --- | --- | --- |
| atualização válida | sucesso, revisão incrementada | recebe o payload atualizado e remove a linha | ausente |
| consumo | not found após aguardar | recebe o payload anterior e remove a linha | ausente |
| atualização com revisão obsoleta | conflito | consumo permanece possível | depende do consumidor |

Não existe resultado em que a linha consumida reaparece. O consumo não recebe
revisão esperada porque a API pública 1.x não oferece esse parâmetro e sua
mudança seria incompatível.

O teste real bloqueia previamente a linha, confirma no `pg_stat_activity` que
as duas conexões independentes aguardam lock, libera a barreira e valida um dos
dois resultados permitidos. A sincronização não depende apenas de atraso
arbitrário.
