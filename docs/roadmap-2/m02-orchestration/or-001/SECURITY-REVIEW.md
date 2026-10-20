# Revisão de segurança

## Controles verificados

- campos desconhecidos são rejeitados;
- payloads, metadados, outputs e detalhes de erro são JSON bounded;
- containers públicos são profundamente imutáveis;
- `condition_ref` não aceita código;
- timestamps funcionais exigem timezone;
- contexto não armazena clients, providers ou ferramentas;
- `tenant_id` não concede autorização;
- erros estruturados não armazenam exceções Python;
- core não importa rede, banco, broker ou provider concreto.

Implementações futuras de autorização devem falhar fechadas. Segredos não
devem ser colocados em payload ou metadados; a OR-001 não oferece cofre nem
criptografia e não transforma um campo serializável em local seguro para
credenciais.
