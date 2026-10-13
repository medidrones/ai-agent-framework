# Decisões concorrentes

A atualização PostgreSQL aceita somente `state = 'pending'`. O primeiro comando
válido incrementa a revisão. Comandos posteriores são aceitos apenas quando
`decision_id`, decisão e identidade são idênticos; qualquer divergência produz
`ApprovalConflictError`.

Foram executados 100 comandos concorrentes alternando approve/reject: um venceu
e 99 foram rejeitados. Separadamente, 100 retries iguais foram admitidos como
idempotentes, mas somente um consumiu o checkpoint.
