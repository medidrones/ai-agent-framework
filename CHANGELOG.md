# Registro de alterações

Todas as alterações relevantes deste projeto serão documentadas neste arquivo.

O formato é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- Fundação inicial do monorepo.
- Estrutura inicial do pacote core.
- Ferramentas de qualidade e integração contínua.
- Documentação inicial de arquitetura e contribuição.
- Contratos fundamentais e modelos imutáveis de agentes.
- Eventos mínimos e abstração assíncrona `Agent`.
- Máquina de estados do lifecycle de execução.
- Transições validadas e histórico ordenado de execução.
- Contratos expandidos de eventos de lifecycle.
- Factory de eventos com sequência monotônica por execução.
- Contratos provider-agnostic para capabilities e descriptors de modelos.
- Mensagens multimodais, requests e responses de modelos.
- Contratos de tool calls e structured output na fronteira do modelo.
- Contabilização de uso por chamada de modelo.
- Eventos estruturados para streaming de modelos.
- Interface `ModelProvider` e hierarquia abstrata de erros.

### Alterado

- O estado genérico `WAITING` foi substituído por estados específicos de
  ferramenta e aprovação.
- O mapa do lifecycle passou a admitir os retornos normativos de ferramentas,
  aprovação e reparo de saída para `RUNNING`, além do processamento sequencial
  de ferramentas e da rejeição terminal de saída.
- `ExecutionLifecycle` agora sempre inicia em `CREATED`; restauração em outro
  estado fica reservada a um contrato futuro.
