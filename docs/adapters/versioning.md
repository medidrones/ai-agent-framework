# Versionamento dos contratos externos

REST usa o prefixo `/v1`, protobuf usa `atlas.agent.v1` e envelopes possuem
`schema_version`. A versão da distribuição Python não substitui a versão do
wire contract.

Mudanças compatíveis podem adicionar campos opcionais com defaults seguros,
novos tipos de evento documentados ou novos endpoints. Clientes devem ignorar
campos desconhecidos nas respostas e tipos de evento que não consomem, sem
inferir autoridade de dados novos.

São incompatíveis: remover ou tornar obrigatório um campo, mudar semântica,
reutilizar número protobuf, alterar tipo ou cardinalidade e renomear status ou
código público. Essas mudanças exigem uma nova versão externa e período de
migração.

O `.proto`, o código gerado, os DTOs REST, os modelos de envelope, os exemplos e
os testes de contrato devem ser atualizados no mesmo commit. Fields protobuf
removidos devem ter nome e número reservados. Eventos persistidos precisam de
upcasters explícitos no adapter específico do broker; o consumer genérico
rejeita versões que não foram configuradas.
