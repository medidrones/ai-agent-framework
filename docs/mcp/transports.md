# Transportes MCP

| Transporte | Situação |
| --- | --- |
| `stdio` | Suportado para processos locais |
| Streamable HTTP | Suportado e recomendado para deploy remoto |
| HTTP+SSE legado | Não implementado como arquitetura Atlas |

`StdioMCPTransportConfig` separa executável e tupla de argumentos. O SDK inicia
o subprocesso sem shell e com ambiente explícito/adicionado à allowlist segura
do SDK. `StreamableHTTPMCPTransport` aceita headers explícitos ou um cliente
HTTP pré-configurado e caller-owned.

Para endpoints remotos use HTTPS. HTTP simples é rejeitado fora de loopback.
O host continua responsável por allowlist de URL, DNS, proxy e política de
egress.
