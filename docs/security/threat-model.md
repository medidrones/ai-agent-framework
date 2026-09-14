# Modelo de ameaças

## Escopo e ativos

Este modelo cobre o SDK Atlas executado dentro de uma aplicação hospedeira. Os
ativos são credenciais, identidade, efeitos de ferramentas, memória,
conhecimento, checkpoints, tokens de retomada, configuração, plugins e
endpoints externos.

## Fronteiras de confiança

```text
Usuário → adapter → runtime → provider
                         ├─→ ferramenta local
                         └─→ servidor MCP
Host → plugin
Configuração → factory
```

Dados de usuário, modelo, ferramenta, retriever, MCP, transportes e configuração
são não confiáveis. Plugins instalados e ativados são código Python com os
privilégios do processo e precisam ser previamente confiados.

## Ameaças e controles

| Ameaça | Controles existentes | Risco residual |
| --- | --- | --- |
| prompt injection | contexto de knowledge não autoritativo, allowlists, guardrails e autorização determinística | guardrails de LLM reduzem risco, mas não são fronteira de segurança |
| uso indevido de ferramenta | registro explícito, allowlist, permissão antes do schema, validação, HITL e limites | a ferramenta autorizada ainda deve aplicar controles do domínio |
| spoofing de identidade | identidade vem de resolver confiável; payload não concede roles | o host deve autenticar o transporte |
| elevação de privilégio | políticas determinísticas e contexto restrito | configuração permissiva continua perigosa |
| vazamento de segredo | referências, tipos secretos, erros normalizados, telemetria allowlisted e scan de artefatos | integrações precisam redigir seus próprios dados |
| plugin malicioso | discovery sem import, ativação explícita, preflight e rollback | não existe sandbox de plugin |
| servidor MCP malicioso | allowlist, normalização, limites e executor comum | o remoto recebe argumentos e pode responder conteúdo hostil |
| resposta malformada | validação Pydantic e protocolo de stream estrito | indisponibilidade externa permanece possível |
| negação de serviço | timeout e limites de turns, tokens e tools | rate limiting distribuído pertence ao host |
| replay | token de uso único, consumo atômico e journal | store não durável não garante operação distribuída |
| configuração adulterada | schema fechado, referências, fingerprint e factories explícitas | integridade do deployment pertence ao host |

## Limites de dados

- Providers externos podem receber mensagens, anexos e schemas de tools e de
  saída estruturada.
- MCP pode transmitir argumentos e resultados fora do processo.
- Adapters escolhidos pela aplicação podem persistir memória e knowledge.
- Observabilidade recebe apenas atributos allowlisted; retenção e exportação
  pertencem ao adapter.
- O core não contém analytics, exportador de telemetria ou acesso de rede e não
  envia dados por conta própria.

## Hipóteses e exclusões

O processo hospedeiro, sistema operacional, instalador e plugins ativados são
confiáveis. O Atlas não promete impedir prompt injection, isolar Python
malicioso, garantir exactly-once distribuído nem substituir autenticação, TLS,
ACL, rate limiting ou gestão de segredos do host.
