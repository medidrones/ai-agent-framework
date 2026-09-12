# Arquitetura de plugins

O sistema de plugins transforma extensões explicitamente compostas em pacotes
distribuíveis sem criar um container global.

```text
ENTRY POINT
  ↓ discover (sem import)
DESCRITOR
  ↓ load explícito
FACTORY → PLUGIN
  ↓ register
MANIFESTO REGISTRADO
  ↓ validate → describe → preflight → activate
CONTRIBUIÇÕES
  ├─ registries injetados: provider, tool, guardrail, evaluator
  └─ host: memory, knowledge, observability
```

## Direção das dependências

`atlas_agents.plugins` depende apenas de contratos públicos do core,
`importlib.metadata` e `packaging`. Ele não depende de SDKs, infraestrutura,
`AgentRuntime` nem da distribuição de avaliação. O suporte a evaluators usa a
fronteira estrutural mínima exigida pelo registry e evita um import inverso de
`atlas_agents.evaluation`.

Plugins externos dependem do core e do SDK que adaptam. Objetos concretos são
encapsulados pelas contribuições tipadas e nunca entram no manifesto ou nos
descritores.

## Atomicidade por plugin

O preflight verifica todos os descritores e conflitos antes de efeitos
colaterais. Depois de `activate()`, o manager valida correspondência um-para-um
entre descritores e contribuições. Registros são realizados na ordem declarada;
uma falha provoca rollback em ordem inversa e limpeza do plugin.

A garantia é por plugin e pressupõe mutação serializada. Plugins ativados com
sucesso anteriormente não são revertidos quando outro plugin falha. Se o
registry falhar também durante rollback, `PluginRollbackError` informa estado
potencialmente inconsistente sem afirmar que o plugin ficou ativo.

## Fronteiras deliberadas

`PluginRegistry` armazena plugins, não serviços arbitrários. `PluginContext`
oferece apenas versão do Atlas e configuração JSON-safe isolada. O manager
recebe registries concretos por parâmetros tipados e não conhece um mapping
genérico de serviços.

Memory, Knowledge e Observability não ganharam registries artificiais. Suas
contribuições permanecem no registro ativo e são obtidas pelo host para compor
managers e runtime no bootstrap.

Não existem autoativação, instalação de pacote, hot reload, watcher ou promessa
de sandbox. Ativar dinamicamente enquanto execuções estão em andamento não é
suportado na versão inicial.
