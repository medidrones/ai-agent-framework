# Falhas de rede

PostgreSQL e Redis foram removidos temporariamente e recriados. Readiness mudou
para indisponível, liveness permaneceu independente dos bancos e não houve
restart loop. Após reconexão, checkpoints confirmados foram retomados.

A NetworkPolicy permite ingress no worker somente a partir do runner rotulado.
Um pod sem esse rótulo recebeu timeout, enquanto o runner obteve `/live`.
Egress dos workers é limitado a DNS, PostgreSQL e Redis.

Também foram executadas perda explícita de DNS durante replacement e partição
temporária do PostgreSQL enquanto uma recuperação mantinha lease. O novo pod
permaneceu not-ready sem DNS; após restaurar a política, tornou-se ready. A
partição não autorizou confirmação stale e o efeito externo permaneceu único.
