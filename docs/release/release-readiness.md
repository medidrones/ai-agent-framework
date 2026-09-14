# Prontidão da release 1.0.0rc3

## Decisão

**READY_FOR_RC.** Todos os gates locais obrigatórios estão verdes, inclusive a
auditoria pública de vulnerabilidades. A matriz publicada em Linux e Windows,
com Python 3.12 e 3.13, também foi aprovada. A promoção para estável ainda exige
certificar os artefatos vinculados à tag e obter os sign-offs formais.

## Evidências obrigatórias

1. Baseline: `534909e`, Python 3.13.15, 1.128 testes, branches 93,00%, sete
   packages e `uv.lock` consistente.
2. Arquitetura: `reports/release/architecture-audit.json`.
3. Ciclos: campo `cycles` do relatório de arquitetura.
4. API pública: `reports/release/public-api.json`.
5. Lifecycle: `test_execution_transition_map.py`.
6. Cancelamento: suítes de runtime, provider, tools, MCP, evaluation e config.
7. Timeout: suítes de runtime, streaming, tools, MCP, REST e gRPC.
8. Concorrência: stress de 100 execuções e testes por subsistema.
9. Cleanup: fechamento de streams, transports, plugins e composição.
10. Segurança: Ruff S, Bandit e auditoria de vulnerabilidades.
11. Canary: testes de segredo e scanner dos artefatos.
12. Identidade: policies e adapters.
13. Tools: permissão, schema, HITL, contagem e executor.
14. HITL: suspensão, aprovação, rejeição e consumo concorrente.
15. Replay: journal e deduplicação por `tool_call_id`.
16. Guardrails: contratos, pipeline e runtime.
17. Memory: contratos, escopo e concorrência.
18. Knowledge/citações: allowlist, RAG e extração final.
19. Provider: contrato comum e OpenAI com cliente fake.
20. Plugins: discovery, compatibilidade, preflight e rollback.
21. MCP: cliente/servidor local, limites, cancelamento e erros.
22. REST: contrato v1, SSE, identidade e erros.
23. gRPC: proto v1, unary/stream, identidade e deadline.
24. Mensageria: envelopes v1, ack/retry e duplicidade.
25. Configuração: schema v1, YAML, segredo, overrides e rollback.
26. Paridade: cenário corporativo e composição declarativa.
27. Performance: `reports/release/performance-baseline.json`.
28. Stress: 100 execuções dentro da suíte bloqueante.
29. Dependências: SBOM com 79 componentes e `pip-audit` sobre 31 dependências de
   runtime, sem vulnerabilidades conhecidas.
30. Segurança estática: Bandit, 20.885 LOC, zero findings; um `nosec`
   revisado no loader derivado de `SafeLoader`.
31. Tipos: mypy estrito, 331 arquivos, zero issues.
32. Lint: Ruff check e format check, 472 arquivos, ambos aprovados.
33. Testes: 1.133 aprovados em Python 3.13.15 e 1.133 aprovados em 3.12.6.
34. Coverage: 93,00% com branches, XML e JUnit gerados localmente e arquivados
   pela CI.
35. Exemplos: 22 cenários executados por teste parametrizado.
36. .NET: builds REST e gRPC.
37. Wheels: sete wheels e sete sdists.
38. Instalação limpa: `scripts/smoke_wheels.py`.
39. Namespace: smoke isolado de `atlas_agents`.
40. Entry points: inspeção e discovery do plugin OpenAI.
41. Artefatos: `reports/release/artifact-security.json`.
42. Compatibilidade: CI e `docs/compatibility.md`.
43. Threat model: `docs/security/threat-model.md`.
44. Produção: `docs/operations/production-checklist.md`.
45. Changelog: seção `1.0.0rc3`.
46. Bundle: 14 distribuições reproduzíveis, SBOM CycloneDX e 15 checksums.
47. Pendências: certificação da tag e sign-offs do gate de aceitação.
48. Recomendação: `READY_FOR_RC`, não `READY_FOR_STABLE`.

## Scorecard

| Categoria | Estado | Evidência |
| --- | --- | --- |
| Arquitetura | PASS | grafo sem ciclos; core sem imports proibidos |
| Correctness | PASS | 1.133/1.133 em Python 3.12 e 3.13 |
| Segurança | PASS | Bandit, AST, artefatos e pip-audit sem findings |
| Performance | PASS | baseline factual gerado |
| Compatibilidade | PASS | Python 3.12/3.13 em Linux e Windows |
| Packaging | PASS | 14 artefatos reproduzíveis e smoke limpo |
| Documentação | PASS | documentação de release e operação revisada |
| Exemplos | PASS | 22 offline, cenário corporativo e clientes .NET |
| Operações | PASS | modelo de ameaças e checklist presentes |

## Resultados medidos

- Grafo: sete packages, zero ciclos e zero dependências proibidas no core.
- API pública: 285 exports no core, 46 em adapters, 70 em config, 55 em
  evaluation, 51 em MCP e 2 em providers.
- Stress: 100 execuções concorrentes com IDs, estados e sequências isolados.
- Benchmark local Windows/Python 3.13.15: 250 execuções, concorrência 25,
  2.815,34 execuções/s; p50 0,300 ms, p95 0,430 ms e máximo 0,904 ms. Esses
  números são baseline comparativo, não SLO.
- Segurança: zero finding do Bandit, zero padrão de alto risco na auditoria AST
  e zero segredo em 14 arquivos de distribuição; `pip-audit` verificou 31
  dependências de runtime e não encontrou vulnerabilidade conhecida.
- Wheels: instalações isoladas core, extensões sem extras e conjunto completo
  passaram `uv pip check`, namespace, `py.typed` e entry point.
- Cross-stack: builds .NET REST/gRPC sem warnings; execute e streaming reais
  passaram nos dois protocolos contra hosts locais.
- Cenário corporativo: status completed, uma citação, um efeito após HITL, dois
  guardrails, 16 spans e avaliação aprovada.

## Findings

- P0/P1 encontrados nas verificações executadas: nenhum.
- Certificação da candidata: aguarda tag imutável, bundle e sign-offs formais.
- Risco residual P2: métricas variam por host; use o baseline somente para
  detectar regressão relativa.
