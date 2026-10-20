# Definição de workflow

Uma definição exige ID, versão PEP 440, nome e pelo menos um nó. IDs de nós
devem ser únicos e toda conexão deve referenciar nós existentes. Esses são
checks estruturais, não validação de DAG.

Os kinds `agent`, `tool`, `gateway`, `join` e `terminal` reservam capacidades
futuras. Nenhum deles declara que há executor implementado. `condition_ref` é
um identificador simbólico; código, expressões Python e chamadas dinâmicas são
rejeitados.
