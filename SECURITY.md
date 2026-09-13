# Política de segurança

## Guardrails

Guardrails são opt-in por agente e falham fechado quando uma avaliação não
produz decisão válida. Transformações de input ocorrem antes de Memory e
Knowledge; chamadas transformadas são revalidadas antes de aprovação ou
execução; e a saída final é avaliada antes de citações e escrita de memória.

Eventos e registros não incluem conteúdo avaliado, argumentos ou resultados.
O core não lê credenciais, carrega módulos, executa shell nem inclui SDK de
moderação. Em streaming, deltas emitidos antes da avaliação pós-acúmulo não
podem ser retirados.

## Observabilidade

A telemetria automática usa allowlists de atributos e não inclui prompts,
input/output, argumentos ou resultados de ferramentas, memória, passagens de
knowledge, justificativas, tokens de retomada, credenciais ou metadata
arbitrária. Exceptions e stack traces não são capturadas por padrão.

IDs técnicos podem ser atributos de spans para correlação, mas nunca labels de
métricas. Adapters são responsáveis por retenção, transporte, redação adicional
e controle de acesso. Falhas do adapter são absorvidas para não alterar o
resultado funcional; essa semântica fail-open não se aplica a guardrails.

## Avaliação

Observations disponibilizam a saída final somente durante a avaliação. O
relatório persiste uma projeção resumida sem output. Conteúdo intermediário,
argumentos e outputs de ferramentas são opt-in; conteúdo de memória, passagens
de knowledge, credenciais, mensagens completas de erro e tokens de retomada não
são capturados por padrão.

O adapter de runtime não neutraliza efeitos externos automaticamente. Avaliações
devem usar memória e checkpoints isolados, ferramentas fake ou sandbox, serviços
de staging, credenciais de teste e dados não produtivos. Inputs enviados a um
LLM judge são não confiáveis e podem conter prompt injection; o score do judge
não constitui verdade factual nem decisão de segurança.

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
- Escopos de memória vazios, globais ou com wildcard são rejeitados.
- Resultados de memória com tipo ou escopo divergente encerram a execução, sem
  contaminar o contexto do modelo.
- Memória é apresentada como dado contextual não confiável; conteúdo, IDs,
  metadados e scores não são registrados em eventos.
- Fontes de conhecimento exigem allowlist explícita por agente; query builders
  não podem ampliar esse conjunto nem habilitar todas as fontes.
- Passagens recuperadas são dados de referência não confiáveis. Conteúdo,
  consulta, URIs, metadados, scores e credenciais não entram em eventos.
- Resultados de fonte não solicitada, passagens duplicadas ou acima do limite
  encerram a execução como violações de protocolo.

## Providers e ferramentas

Configurações declarativas são tratadas como entrada não confiável. O loader
usa YAML seguro, rejeita chaves duplicadas e campos desconhecidos e nunca
executa import dinâmico, `eval`, `exec`, leitura implícita de ambiente ou busca
remota. Segredos aparecem na árvore somente como referências e são resolvidos
por um contrato injetado no ponto de uso. MCP e adapters permanecem
desabilitados por padrão. Consulte
[`docs/config/security.md`](docs/config/security.md).

Providers deverão receber credenciais por configuração ou serviços de segredos
injetados, sem expô-las em eventos ou exceções. Ferramentas declaram entradas e
permissões em `ToolDefinition`; dependências são injetadas diretamente em seus
construtores, não obtidas de um container no contexto da execução.

Conteúdo vindo de modelos, ferramentas ou bases de conhecimento nunca concede
autoridade adicional por si só. Um executor genérico de código permanece
explicitamente fora do escopo inicial.

### Providers externos

Ao usar o provider OpenAI, mensagens, schemas de ferramentas, schemas de saída
estruturada e referências de imagens da requisição atravessam a fronteira do
processo e são enviados ao serviço externo. A aplicação deve aplicar suas
políticas de classificação, consentimento e retenção antes da chamada.

Credenciais são fornecidas explicitamente ao cliente ou à configuração do
plugin. Metadata do request, identidade, IDs internos e tokens de retomada não
são encaminhados automaticamente. O provider define `store=False` por padrão;
alterar essa política exige configuração explícita. Clientes injetados
manualmente pertencem ao chamador, enquanto o plugin fecha apenas o cliente que
ele cria.

### Model Context Protocol

Servidores MCP remotos são fronteiras externas não confiáveis. Ferramentas,
schemas, recursos, prompts, conteúdo e erros recebidos são validados e
normalizados antes de alcançar o core. Nada é importado automaticamente: cada
ferramenta exige allowlist explícita, recebe nome local determinístico e passa
pelo `ToolExecutor`, preservando permissões, guardrails, aprovação humana,
deduplicação e limites antes da chamada remota.

O servidor MCP do Atlas também falha fechado: somente ferramentas, recursos e
prompts registrados explicitamente são expostos. Ferramentas são executadas pelo
`ToolExecutor`; identidade e autoridade não são inferidas de metadata enviada
pelo cliente. Configurações de transporte não executam shell, rejeitam URLs com
credenciais e não exibem ambiente ou headers em representações e erros.

HTTP sem TLS é aceito apenas em loopback para desenvolvimento. Em produção,
aplicações devem usar HTTPS, aplicar autenticação e autorização na borda,
restringir origens e redirecionamentos e controlar egress. Consulte
[`docs/mcp/security.md`](docs/mcp/security.md).

### Adapters externos

REST, gRPC e mensageria recebem dados não confiáveis. A identidade deve ser
obtida exclusivamente de middleware, interceptor ou contexto de entrega já
autenticado; campos do payload nunca concedem roles ou permissões. Cada host
deve injetar uma política de acesso e tetos de execução, configurar TLS, limites
de corpo/mensagem, rate limiting e isolamento por tenant.

Tokens de retomada permanecem no body e devem ser tratados como bearer secrets.
O store de idempotência em memória não é durável nem oferece exactly-once; uma
implantação distribuída precisa de reserva atômica persistente e, quando
necessário, inbox/outbox. Consulte
[`docs/adapters/security.md`](docs/adapters/security.md).

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

Memória não é habilitada pela mera presença de um store. Cada agente declara os
tipos permitidos, e uma policy de escrita não pode ampliar essa allowlist.
Adapters devem garantir o isolamento exato de `MemoryScope` em `get`, `search`,
`write` e `delete`. O core não detecta automaticamente segredos no conteúdo;
policies e aplicações devem aplicar classificação, consentimento, retenção e
redação adequados antes de persistir dados sensíveis.

Retrievers recebem somente IDs formais, identidade e metadata segura
explicitamente fornecida. Clientes e credenciais devem ser injetados no
construtor do adapter. Filtros da consulta não constituem uma barreira de
autorização: cada implementação continua responsável por ACLs da fonte. URIs de
citação podem ser expostas no resultado e não devem conter tokens ou segredos.

## Plugins

Plugins do Atlas são código Python confiável. Ativar um plugin instalado
executa código com os mesmos privilégios do processo Python hospedeiro. O Atlas
não executa plugins em sandbox. Instale e ative somente plugins de fontes
confiáveis.

Discovery não importa plugins e ativação nunca é automática. O loader aceita
somente entry points descobertos no grupo oficial, sem import strings
arbitrárias. O core não instala dependências, não lê credenciais do ambiente e
não expõe configuração em `PluginInfo`, resultados ou erros. Preflight impede
sobrescrita silenciosa; rollback reduz registros parciais, mas uma falha do
próprio registry durante rollback pode deixar o host inconsistente e exige
intervenção. Consulte [`docs/plugins/security.md`](docs/plugins/security.md).
