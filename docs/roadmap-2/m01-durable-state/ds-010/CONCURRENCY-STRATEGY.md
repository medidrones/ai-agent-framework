# Estratégia de concorrência

`revision` começa em 1 e pertence ao armazenamento, não ao schema do payload.
O CAS Lua compara revisão, estado, expiração e identidades no Redis e incrementa
a revisão na mesma operação. Não existe retry automático ou lock Python.

Testes reais provaram um único vencedor entre 12 writers concorrentes e ausência
de lost update. Update e consume podem ambos concluir somente na ordem válida
update→consume; se consume linearizar primeiro, o update é rejeitado.

Lease/fencing distribuído não é implementado pela DS-010. A capability leased
fica indisponível até protocolo próprio e testes da DS-011.
