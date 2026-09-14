# Checklist de produção

Os exemplos oficiais comprovam integração local e não são configuração de
segurança para produção.

- [ ] mapear identidade autenticada sem confiar no payload;
- [ ] configurar acesso a agentes e isolamento por tenant;
- [ ] restringir permissões e allowlists de ferramentas;
- [ ] exigir HITL para efeitos relevantes e usar checkpoint store durável;
- [ ] definir limites de turns, tools, tokens, orçamento, timeout e mensagem;
- [ ] injetar segredos com segurança, sem `.env` em artefatos ou logs;
- [ ] habilitar TLS e autenticação em REST, gRPC, broker e MCP;
- [ ] limitar egress e revisar endpoints, redirects e servidores MCP;
- [ ] revisar origem, versão e privilégios de plugins;
- [ ] configurar observabilidade, redação, retenção e acesso;
- [ ] usar idempotência durável e atômica em mensageria;
- [ ] definir retenção, consentimento e exclusão de memória;
- [ ] aplicar ACL nas fontes de knowledge;
- [ ] validar os mesmos wheels usados no deployment;
- [ ] ensaiar cancelamento, indisponibilidade e rollback;
- [ ] verificar checksums e SBOM da candidata.

Monitore falhas, timeouts, rejeições e consumo sem registrar prompts, outputs,
tokens de retomada ou credenciais. P0 bloqueia qualquer release; P1 bloqueia a
versão estável.
