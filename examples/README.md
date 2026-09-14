# Exemplos oficiais do Atlas

Esta suíte é uma especificação executável da API pública. Os exemplos evoluem do runtime mínimo até uma referência corporativa completa. Código e identificadores permanecem em inglês; documentação e mensagens voltadas ao usuário estão em português do Brasil.

## Sequência recomendada

| Faixa | Foco |
| --- | --- |
| 01–04 | Fundamentos, streaming e saída estruturada |
| 05–07 | Ferramentas, multi-turn e HITL |
| 08–12 | Memória, RAG, guardrails, observabilidade e avaliação |
| 13–15 | Extensibilidade e MCP |
| 16–21 | Adapters e interoperabilidade Python/.NET |
| 22 | Arquitetura de referência integrada |

Cada diretório possui instruções, saída esperada, notas de segurança e considerações de produção. Todos os cenários Python, exceto o provider OpenAI explicitamente opt-in, funcionam offline com fixtures determinísticas.

## Validação

A suíte automatizada verifica estrutura, imports públicos, execução offline e
compilação dos consumidores .NET REST e gRPC. Execute na raiz:

```bash
uv run pytest
```

Consulte [22_enterprise_reference](22_enterprise_reference/README.md) para o fluxo consolidado.
