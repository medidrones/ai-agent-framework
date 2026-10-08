# TTL, retenção e tombstones

O Redis `TIME` é a autoridade temporal. Expiração lógica é avaliada dentro dos
scripts antes de lease, CAS ou consumo. No limite, o estado passa a `expired` e
o payload é removido.

O TTL físico aponta para o fim da retenção, não para a expiração lógica. Consumo
recalcula `retention_until_ms`, preserva receipt e fencing generation e remove
somente os dados que não são necessários à auditoria/replay.

Cleanup Redis adicional não é anunciado pela DS-011; qualquer rotina futura
deverá respeitar essas mesmas janelas.
