# Post para LinkedIn — arquitetura do Atlas Agent Framework

## Assets para publicação

Os formatos têm finalidades diferentes e devem ser preservados:

- [`atlas-v1-architecture.png`](../architecture/atlas-v1-architecture.png):
  primeira imagem do post no LinkedIn;
- [`atlas-roadmap-2-architecture.png`](../architecture/atlas-roadmap-2-architecture.png):
  segunda imagem do post no LinkedIn;
- os arquivos SVG correspondentes são as fontes vetoriais usadas na
  documentação técnica do GitHub.

## Texto principal

Como construir um framework de agentes sem transformar o core em um catálogo
de SDKs, bancos e frameworks?

Essa foi a pergunta que guiou a arquitetura do **Atlas Agent Framework 1.0.1**.

Em vez de começar pelo provider, começamos pelos contratos. O núcleo define
agentes, modelos, lifecycle, streaming, estado e execução multi-turn sem
conhecer OpenAI, FastAPI, gRPC, brokers ou qualquer infraestrutura concreta.

Ao redor dele, capacidades como ferramentas, Human-in-the-Loop, memória,
Knowledge/RAG, guardrails e observabilidade entram por APIs explícitas e
injeção de dependência. Nas bordas ficam os elementos substituíveis: providers,
adapters, MCP, stores, retrieval e telemetria.

Algumas decisões importantes:

• APIs async-first e tipagem estrita  
• modelos imutáveis e Pydantic nas fronteiras  
• autorização e validação antes de executar ferramentas  
• conteúdo recuperado tratado como dado não confiável  
• plugins opcionais, com preflight e rollback  
• core sem acesso direto à rede ou a segredos  
• compatibilidade pública preservada entre integrações

O resultado foi publicado em **sete distribuições Python**, permitindo instalar
somente o necessário — do core mínimo ao meta-package completo.

A versão 1.0.1 passou por certificação dos artefatos, instalação limpa, testes
de regressão e verificação de integridade antes da publicação no PyPI e no
GitHub.

Mais do que adicionar funcionalidades, o trabalho foi definir fronteiras que
continuem fazendo sentido quando novos providers, ferramentas e transportes
forem incorporados.

Com a fundação publicada, o próximo ciclo será o **Roadmap 2 — Ecosystem &
Enterprise**. O objetivo não é redesenhar o runtime, mas expandir as
implementações ao redor dos contratos já estabilizados:

• estado durável com PostgreSQL e Redis  
• memória e Knowledge/RAG enterprise  
• novos providers e OpenTelemetry  
• RabbitMQ, Kafka e mensageria cloud  
• SDKs oficiais .NET e TypeScript  
• suites de conformidade, hardening e uma baseline Atlas 1.x LTS

O primeiro passo será certificar o contrato de `CheckpointStore` antes de
escrever qualquer adapter persistente. A regra para toda a linha 1.x é simples:
**expandir implementações, preservar contratos**.

🔗 Repositório: https://github.com/medidrones/ai-agent-framework  
📦 Release: https://github.com/medidrones/ai-agent-framework/releases/tag/v1.0.1

#Python #SoftwareArchitecture #AIAgents #OpenSource #DeveloperTools

## Texto alternativo da imagem

Diagrama da arquitetura do Atlas Agent Framework 1.0.1. Aplicações, serviços e
automações acessam camadas opcionais de configuração, adapters e plugins. No
centro está o pacote provider-neutral atlas-agent-core, com contratos públicos,
runtime e lifecycle, ferramentas e aprovação humana, memória, Knowledge/RAG,
guardrails e observabilidade. Nas bordas ficam provider OpenAI, MCP, stores,
retrieval e telemetria, todos dependentes dos contratos do core.

## Texto alternativo da segunda imagem

Diagrama do Roadmap 2 do Atlas Agent Framework. A versão 1.0.1 publicada é a
baseline congelada. A evolução começa por Durable State, Enterprise Memory e
Enterprise Knowledge; depois se divide em expansão de providers e
observabilidade, convergindo em mensageria, SDKs multiplataforma, conformidade,
hardening e Atlas 1.x LTS. APIs permanecem aditivas e o AgentRuntime não é
redesenhado. Multi-agent e workflow graphs ficam para o Atlas 2.x.

## Sugestão de primeira linha alternativa

**O desafio não era integrar mais um modelo. Era garantir que o framework não
dependesse de nenhum deles.**
