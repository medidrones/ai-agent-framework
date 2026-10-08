# Matriz de estados de ownership

| Estado atual | Operação | Resultado |
| --- | --- | --- |
| sem linha e checkpoint ativo | acquire | owner ativo, token 1 |
| lease ativo | acquire por outro owner | conflito controlado |
| lease expirado | acquire | novo owner, token incrementado |
| lease ativo correto | renew | expiração não regressiva |
| owner/token obsoleto | renew/release | lease perdido |
| lease ativo correto | release | owner e timestamps nulos; token preservado |
| checkpoint consumido/expirado | acquire | não encontrado |
| lease válido + revisão correta | CAS protegido | atualização e revisão incrementada |
| lease obsoleto | CAS/consume protegido | rejeição atômica |

Double release resulta em `CheckpointLeaseLostError`, uma resposta controlada e
determinística.
