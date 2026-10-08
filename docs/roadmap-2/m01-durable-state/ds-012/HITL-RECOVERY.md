# Recuperação HITL

O checkpoint permanece suspenso até uma decisão externa real. A política
`AuthorizedHITLRecoveryPolicy` revalida lifecycle e aprovação sob ownership; o
invoker chama somente `AgentRuntime.resume` ou `resume_stream`.

Os testes reais validam restart de runtime, identidade inválida sem consumo,
rejeição sem execução de ferramenta e 100 resumes concorrentes com um único
vencedor. Aprovação ausente, rejeitada ou expirada falha fechado.

Nenhum dado do checkpoint fabrica identidade ou aprovação.
