# Injeção de falhas

Foram exercitados:

- `os._exit` em processos independentes após checkpoint confirmado;
- exceções em discovery, eligibility, load, invoker e persistência do resultado;
- timeout e cancellation;
- lease expirado/perdido e fencing obsoleto;
- payload corrompido e versão incompatível;
- cliente Redis indisponível e resultado de consumo reconciliado;
- reinício real dos servidores PostgreSQL e Redis.

Mocks validam lógica pura; os gates de infraestrutura usam serviços reais. O probe
reproduzível é `scripts/certify_ds012_restart.py`.
