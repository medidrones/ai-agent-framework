# Cancellation e deadlines

`CancelledError` é propagado pelo coordinator após registrar a tentativa como falha
em best effort e liberar o lease no `finally`. `asyncio.wait_for` limita a tentativa
sem converter timeout em sucesso.

O checkpoint preserva `remaining_timeout_seconds`; o restorer reduz o orçamento
pela passagem do tempo, sem reiniciar o deadline absoluto. Cancellation, deadline
vencido e limite de tentativas também são decisões bloqueantes na política DS-012.

Evidências: testes de cancellation, timeout, restauração temporal, cleanup e
`attempt_limit_survives_new_recorder_instance`.
