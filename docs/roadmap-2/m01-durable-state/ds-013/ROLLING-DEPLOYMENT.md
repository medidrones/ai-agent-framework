# Rolling deployment

O Deployment usa duas réplicas, `maxUnavailable: 1`, `maxSurge: 1` e PDB com
`minAvailable: 1`. Rolling restart durante checkpoints pendentes preservou HITL,
não perdeu checkpoint e não duplicou efeitos. O benchmark mediu 6.353,640 ms.

A certificação cobre revisões compatíveis do host sobre Atlas `1.0.1`. Não se
declara compatibilidade entre releases Atlas incompatíveis ou schemas fora da
matriz certificada na DS-009.
