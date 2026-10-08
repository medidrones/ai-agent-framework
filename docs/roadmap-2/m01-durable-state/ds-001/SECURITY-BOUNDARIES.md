# Fronteiras de segurança

## Controles existentes

- `ResumeToken.create()` usa `secrets.token_urlsafe(32)`.
- O token não entra em eventos, telemetria ou no checkpoint.
- A solicitação de aprovação apresenta nome da ferramenta e nomes das chaves,
  não os valores dos argumentos.
- Metadata exige valores JSON compatíveis.
- O core não acessa rede, banco ou variáveis de ambiente para obter segredos.
- Provider, ferramenta, permissão e schema são revalidados na retomada.

## Modelo de ameaça

O token funciona como bearer capability. Quem o obtém pode tentar consumir o
checkpoint. O adapter deve aplicar hash/HMAC no índice quando apropriado,
comparação segura, criptografia em trânsito e repouso, autorização e isolamento
por tenant, além de nunca registrar token ou payload completo.

O checkpoint contém argumentos completos da ferramenta, mensagens, contexto e
metadata; esses campos podem transportar dados sensíveis. A regra atual de
“livre de segredos” é uma obrigação do chamador, não uma validação estrutural.

## Achados

- `DS001-GAP-004`: o store não recebe escopo de tenant/owner; a autorização é
  externa ao contrato.
- `DS001-GAP-010`: `ResumeToken.value` aparece no `repr` padrão do modelo.
- `DS001-GAP-011`: não há classificação ou redaction de conteúdo sensível no
  payload persistido.

Nenhum teste ou documento deve imprimir tokens reais. A marca sintética usada
na auditoria confirmou a exposição no `repr` sem envolver credenciais.
