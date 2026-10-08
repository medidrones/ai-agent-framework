# Estratégia de idempotência

`consume_authorized_identified` recebe um `operation_id` estável, não sensível,
com até 128 caracteres ASCII seguros. O identificador é persistido atomicamente
com o consumo. `reconcile_consumption` distingue:

- `APPLIED`: esta tentativa realizou o consumo;
- `AVAILABLE`: nenhuma tentativa consumiu o checkpoint;
- `NOT_APPLIED`: outra tentativa venceu;
- `UNKNOWN`: falta evidência suficiente.

O identificador não substitui autorização e não torna efeitos externos
exactly-once. Em resultado ambíguo, o chamador reconcilia antes de decidir por
qualquer retry.
