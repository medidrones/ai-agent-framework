# Contrato de lease

`CheckpointLease` é imutável, tipado e contém checkpoint, owner, fencing token
positivo e timestamps com fuso horário. `CheckpointLeaseManager` oferece
`acquire`, `renew` e `release` assíncronos.

Erros controlados:

- `CheckpointLeaseConflictError`: outro owner mantém lease ativo;
- `CheckpointLeaseLostError`: geração expirada, liberada ou substituída;
- `CheckpointLeaseNotFoundError`: checkpoint ausente, expirado ou consumido.

O `owner_id` identifica o worker para coordenação, mas não substitui identidade
autenticada nem autorização de negócio. Duração deve ser positiva e o adapter
usa exclusivamente o relógio do PostgreSQL para validade transacional.
