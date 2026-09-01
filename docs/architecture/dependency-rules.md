# Regras de dependência

Estas regras preservam o Atlas como um framework incorporável, sem acoplá-lo a
uma aplicação ou stack de infraestrutura específica.

## Pacote core

O pacote core pode depender somente de bibliotecas de uso geral necessárias
para validação, serialização, tipagem e comportamento neutro de provedor.

Ele não deve importar nem exigir:

- SDKs de provedores de modelos;
- frameworks web;
- drivers de bancos de dados ou mapeadores objeto-relacionais;
- clientes de message brokers;
- clientes de bancos de dados vetoriais;
- clientes de telemetria específicos de infraestrutura;
- pacotes de domínios de negócio.

O core não deve ler segredos de variáveis de ambiente, usar registries globais
mutáveis, executar código arbitrário ou expor valores específicos de provedores
por interfaces públicas.

## Plugins

Plugins implementam contratos declarados pelo core. Um plugin pode depender do
SDK que integra, mas essa dependência permanece em sua própria distribuição. Os
plugins não devem depender de adapters de transporte.

## Adapters

Adapters traduzem dados entre transportes externos e a API pública do core.
Eles podem depender do core e de bibliotecas de transporte. O core nunca deve
importar um adapter.

## Garantia das regras

Cada pacote declara suas dependências de forma independente. A integração
contínua executa lint, verificação estrita de tipos, testes e builds dos pacotes.
Testes de arquitetura serão adicionados quando existirem imports entre pacotes
que possam ser validados de forma significativa.
