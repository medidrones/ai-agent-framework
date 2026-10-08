# Integridade referencial

## Decisão

O modelo não usa foreign keys entre os agregados duráveis. Essa ausência é
intencional, não um gap: checkpoint, lease, tentativa de recovery, tombstone e
auditoria possuem ciclos de vida e retenção distintos. Uma cascade apagaria
evidência de replay/auditoria; uma FK restritiva impediria o consumo ou purge
atômico que deve preservar tombstones e histórico.

A consistência lógica é garantida pelas transações e predicados dos adapters:

- lease só é adquirido para execução com checkpoint ativo;
- recovery exige checkpoint e geração de lease vigentes;
- consume remove checkpoint e cria tombstone na mesma transação;
- purge revalida lease, recovery, retenção e legal hold sob lock;
- auditoria sobrevive ao registro operacional excluído.

## Constraints certificadas

PKs impedem duplicidade de identidade; UNIQUE impede repetição de número de
tentativa e `operation_id`; CHECKs impedem revisão/fencing inválidos, intervalos
temporais invertidos, estado parcial de lease, conclusão parcial e enums SQL
fora do domínio.

`unexpected_orphan_records = 0` significa ausência de violação dessas regras
lógicas. Registros intencionalmente sobreviventes (tombstone e auditoria) não
são órfãos e não devem receber cascade.
