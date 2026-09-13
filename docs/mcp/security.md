# Segurança MCP

- Tools remotas não são importadas automaticamente.
- Tools locais não são expostas automaticamente.
- Annotations remotas não são autorização.
- Metadata e argumentos não são identidade.
- Headers e ambiente ficam fora de `repr`, erros e eventos.
- Não há shell, descoberta mágica de executável, retries ou reconnect ocultos.
- Resources não habilitam filesystem e prompts não alteram agentes.
- OAuth/OIDC pertencem ao host e ao SDK; o Atlas não inventa autenticação.
- Sampling, Roots, Logging legado, elicitation/HITL e extensions de UI não são
  integrados nesta versão.

O endpoint remoto é uma fronteira SSRF. Quando a URL vier de configuração não
confiável, o host deve impor allowlists, DNS seguro, proxy e controles de rede.
