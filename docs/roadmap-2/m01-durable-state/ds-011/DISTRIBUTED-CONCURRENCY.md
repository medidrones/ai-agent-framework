# Concorrência distribuída

Testes reais executados contra Redis 7.4.11:

| Cenário | Resultado |
| --- | --- |
| 10 processos independentes | 1 consumo, 9 rejeições |
| 100 consumidores assíncronos | 1 consumo, 99 rejeições |
| 100 resumes HITL aprovados | 1 resultado, 99 rejeições, 1 tool call |
| update versus consume | estado final consistente |

Os processos criam clientes próprios; portanto, o resultado não depende de um
lock, loop de eventos ou conexão compartilhada no processo de teste.
