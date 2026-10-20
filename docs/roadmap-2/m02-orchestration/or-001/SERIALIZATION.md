# Serialização e limites

Dados públicos aceitam somente valores JSON: null, booleanos, números finitos,
strings, arrays e objetos com chaves string. Containers são copiados e
convertidos recursivamente em estruturas imutáveis; a serialização os devolve
como arrays e objetos JSON comuns.

| Limite | Valor | Justificativa |
| --- | ---: | --- |
| identificador/chave | 255 caracteres | evita IDs ambíguos e abuso de índices futuros |
| string JSON | 65.536 caracteres | limita entrada individual sem impor transporte |
| profundidade | 32 níveis | evita exaustão recursiva |
| itens | 10.000 | limita amplificação de memória |

Os limites são fixos nesta primeira versão pública. Evolução configurável deve
ser aditiva. Estruturas recursivas, callables, objetos arbitrários, NaN,
infinito, `pickle`, `eval` e `exec` são rejeitados ou proibidos.
