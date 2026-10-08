# Testes de concorrência

Os testes usam PostgreSQL 16 real, conexões independentes e, no cenário
multiprocesso, dois processos `spawn` com pools próprios.

Evidências cobertas:

- duas chamadas concorrentes descobrem o mesmo checkpoint e somente uma o
  consome;
- dois processos produzem exatamente uma recuperação durável;
- lease expirado durante o invoker impede consumo;
- novo fencing token rejeita a conclusão do owner antigo;
- limite de tentativa persiste entre instâncias do recorder;
- tentativa incompleta sobrevive ao restart e a seguinte é numerada como 2;
- filtro de tenant impede descoberta fora do escopo;
- checkpoint consumido não reaparece para replay.

Esses testes certificam autorização at-most-once do checkpoint, não
exactly-once de efeitos externos.
