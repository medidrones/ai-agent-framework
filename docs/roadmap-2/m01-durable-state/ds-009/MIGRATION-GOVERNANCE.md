# Governança de migrations

| Revisão | Responsabilidade | Natureza |
| --- | --- | --- |
| 001 | checkpoint store | criação |
| 002 | concorrência otimista | expansão aditiva |
| 003 | leases e fencing | criação |
| 004 | tentativas de recovery | criação |
| 005 | retenção e tombstones | expansão aditiva |
| 006 | legal hold e auditoria de purge | expansão aditiva |
| 007 | índice de candidatos de recovery | índice aditivo |

Os arquivos 001–006 não foram modificados. Cada arquivo é lido dos recursos do
pacote, recebe SHA-256 e é registrado em `schema_migrations`. O runner adquire um
advisory lock transacional, valida o histórico inteiro e aplica SQL + registro
na mesma transação.

O parâmetro opcional `target_version` serve para reprodução e rollout
controlados. Ele aceita apenas 1..7, não realiza downgrade e rejeita um banco
mais novo que o alvo. Histórico com versão desconhecida, lacuna ou checksum
divergente interrompe a operação com erro seguro.

Migrations não são executadas no import nem na construção dos adapters. A
automação de deployment deve executar o migrator com uma identidade própria e
somente depois liberar readiness do runtime.
