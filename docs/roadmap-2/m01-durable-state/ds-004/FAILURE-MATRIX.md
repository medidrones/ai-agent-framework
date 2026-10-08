# Matriz de falhas

| Cenário | Resultado certificado |
| --- | --- |
| dois ou dez consumidores | um sucesso; demais recebem not found seguro |
| processos independentes | um commit vencedor |
| replay do token/checkpoint | rejeitado sem nova ferramenta |
| token desconhecido/expirado | rejeitado antes do validator |
| identidade ou request inválido | rollback; checkpoint preservado |
| decisão rejeitada válida | consumo confirmado; ferramenta não executada |
| payload inválido | rollback no caminho autorizado |
| falha antes do commit | rollback |
| cancelamento aguardando lock | `CancelledError`, cleanup e rollback |
| pool fechado/indisponível | erro de infraestrutura seguro |
| restart após commit | consumo permanece confirmado |
| corrida CAS/consume | serialização por lock; estado consistente |
| crash depois do commit | checkpoint permanece consumido; reconciliação externa |
| store 1.x sem capability | fallback compatível com semântica histórica |

Ausente, expirado e consumido convergem deliberadamente para a mesma exceção
segura do contrato 1.x. O adapter distingue sucesso, rejeição por ausência e
falha de infraestrutura, mas não cria um oracle externo sobre o ciclo de vida
do token. Conflitos de revisão permanecem tipados pela capability CAS.

Não há retry automático quando a confirmação do commit fica ambígua.
