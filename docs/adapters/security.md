# Segurança dos adapters externos

Transportes são fronteiras não confiáveis. A aplicação hospedeira continua
responsável por autenticação, TLS, proteção contra abuso, auditoria e isolamento
de tenants.

## Requisitos de implantação

- construa `TransportPrincipal` somente depois de validar a credencial;
- injete uma `AgentAccessPolicy` que falhe fechado;
- aplique tetos do servidor para turnos, tools, tokens, timeout e budget;
- limite tamanho, concorrência e taxa também no proxy, servidor ou broker;
- trate metadata, anexos, mensagens e contexto como dados não confiáveis;
- nunca registre bodies, claims, tokens de retomada ou credenciais;
- proteja respostas de idempotência e checkpoints com o mesmo isolamento da
  execução original;
- use TLS e, quando adequado, mTLS entre serviços.

Os DTOs rejeitam campos desconhecidos para reduzir identity spoofing. O mapper
padrão não promove claims para autoridade. `AllowAllAgentAccessPolicy` e as
factories anônimas são opções explícitas para redes internas confiáveis, não
defaults de segurança.

Tokens de retomada são segredos bearer. Eles ficam no body protobuf/JSON, são
ocultados de `repr` e não entram nos envelopes publicados. URLs de anexos e
citações não devem conter credenciais. O core deve usar um `CheckpointStore`
com consumo atômico para impedir replay.

Mensagens públicas de erro não incluem stack trace nem exception original.
Observabilidade adicional deve usar allowlists e redação. Para HTTP chunked,
payload comprimido ou mensagens grandes do gRPC/broker, configure limites na
camada de infraestrutura: a validação do DTO não substitui esses controles.
