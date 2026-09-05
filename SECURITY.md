# Política de segurança

## Versões compatíveis

O Atlas Agent Framework é um software em fase de pré-lançamento. Correções de
segurança são aplicadas à revisão mais recente da branch padrão.

## Como relatar uma vulnerabilidade

Não divulgue vulnerabilidades em uma issue pública. Relate-as de forma privada
aos mantenedores usando o recurso de comunicação de segurança oferecido pelo
serviço que hospeda o repositório. Inclua os passos para reprodução, as versões
afetadas, o impacto e qualquer mitigação sugerida.

Os mantenedores devem confirmar o recebimento em até cinco dias úteis e fornecer
atualizações enquanto o relato estiver sob investigação.

## Princípios de segurança

- Segredos são injetados explicitamente e nunca registrados ou serializados.
- Credenciais, tokens, chaves privadas e arquivos `.env` não devem ser
  versionados.
- O core não lê credenciais diretamente de variáveis de ambiente.
- Os argumentos das ferramentas são validados antes da execução.
- Conteúdo recuperado ou gerado por modelos é tratado como não confiável.
- A execução arbitrária de código não faz parte do runtime do core.
- O acesso à rede é introduzido somente por adapters explícitos.
- O executor resolve somente ferramentas registradas, verifica autorização
  antes do schema e valida argumentos antes de chamar a implementação.
- O runtime oferece ao modelo somente a allowlist declarada pelo agente e
  rejeita ferramentas registradas que estejam fora dela.
- Nomes de ferramentas nunca disparam import dinâmico, shell, `eval` ou `exec`.
- Solicitações de aprovação expõem apenas nome, ID e chaves dos argumentos da
  ferramenta, sem seus valores completos.
- Tokens de retomada são opacos, imprevisíveis, de uso único e não entram em
  eventos ou checkpoints.
- Checkpoints não contêm providers, ferramentas, credenciais, locks ou objetos
  de infraestrutura; o store é um adapter explicitamente injetado.

## Providers e ferramentas

Providers deverão receber credenciais por configuração ou serviços de segredos
injetados, sem expô-las em eventos ou exceções. Ferramentas declaram entradas e
permissões em `ToolDefinition`; dependências são injetadas diretamente em seus
construtores, não obtidas de um container no contexto da execução.

Conteúdo vindo de modelos, ferramentas ou bases de conhecimento nunca concede
autoridade adicional por si só. Um executor genérico de código permanece
explicitamente fora do escopo inicial.

`ToolExecutionResult` não retém exceptions, stack traces nem output parcial em
falhas. Erros inesperados são substituídos por mensagem pública genérica. A
semântica de idempotência permanece declarativa e não oferece garantia
distribuída. O runtime deduplica apenas `tool_call_id` dentro de uma execução:
payload idêntico reutiliza o resultado já registrado, enquanto payload
conflitante encerra a execução com segurança.

Ferramentas em modo `REQUIRED` ou aprovadas por policy são suspensas antes do
contador e da execução. O `CheckpointStore.consume()` deve ser atômico para
impedir replay e retomadas concorrentes. O core não fornece UI, autoaprovação,
persistência concreta nem espera bloqueante por decisão humana.
