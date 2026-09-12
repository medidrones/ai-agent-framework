# Segurança de plugins

Plugins do Atlas são código Python confiável. Ativar um plugin instalado
executa código com os mesmos privilégios do processo Python hospedeiro. O Atlas
não executa plugins em sandbox.

Instale e ative somente plugins de fontes confiáveis. Revise a distribuição,
suas dependências e a factory publicada antes da ativação.

## Garantias do core

- discovery lista apenas o grupo `atlas_agents.plugins` e não importa módulos;
- load parte somente de um descritor descoberto, sem aceitar import string
  arbitrária;
- não há `eval`, `exec`, shell, pip dinâmico ou `pkg_resources`;
- ativação é explícita e nunca ocorre para todos os pacotes instalados;
- `PluginContext` não contém registries, runtime, logger nem container;
- conflitos são verificados antes de `activate()`;
- contribuições nunca sobrescrevem registros silenciosamente;
- configuração não entra em resultados, introspecção ou mensagens de erro;
- erros públicos não exigem traceback nem propagam mensagens cruas do plugin.

O core não lê segredos do ambiente. O host pode fornecer credenciais por
configuração explícita, e o plugin concreto continua responsável por usá-las e
descartá-las com segurança. Como código confiável no mesmo processo, um plugin
malicioso ainda pode acessar tudo o que o processo permitir; os controles acima
reduzem comportamento mágico, mas não formam uma barreira de isolamento.

Ativação ou desativação concorrente, hot reload durante execuções e observação
de alterações de pacotes não são suportados nesta versão. O host deve serializar
mutações e concluir o bootstrap antes de iniciar tráfego.
