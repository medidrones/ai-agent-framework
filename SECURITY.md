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
- O core não lê credenciais diretamente de variáveis de ambiente.
- Os argumentos das ferramentas são validados antes da execução.
- Conteúdo recuperado ou gerado por modelos é tratado como não confiável.
- A execução arbitrária de código não faz parte do runtime do core.
- O acesso à rede é introduzido somente por adapters explícitos.
