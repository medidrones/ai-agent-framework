# Política de API pública

São públicos somente os nomes exportados intencionalmente por `__all__` nos
entry points documentados e os paths explicitamente usados na documentação.
Os entry points canônicos são:

- `atlas_agents` para o core;
- `atlas_agents.adapters` e seus módulos `rest`, `grpc` e `events`;
- `atlas_agents.config`;
- `atlas_agents.evaluation`;
- `atlas_agents.mcp`;
- `atlas_agents.providers` e `atlas_agents.providers.openai`;
- `atlas_agent` para metadata do meta-package.

Módulos ou nomes iniciados por `_`, código protobuf gerado e imports profundos
não documentados são internos. Sua alteração não constitui quebra pública.

Após 1.0, mudanças incompatíveis em exports estáveis exigem major e seguem a
janela de depreciação. Antes de 1.0, mudanças são registradas no changelog e
devem oferecer orientação de migração. APIs experimentais precisam ser
marcadas na documentação e podem mudar sem a janela normal.

Somente representações declaradas como wire contract possuem estabilidade de
serialização. O fato de um modelo Pydantic aceitar `model_dump()` não transforma
sua representação interna em protocolo público.
