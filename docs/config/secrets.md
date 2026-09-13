# Referências de segredos

Segredos nunca devem aparecer diretamente no YAML. Declare somente uma
referência:

```yaml
providers:
  openai:
    type: openai
    config:
      api_key:
        secret_ref: openai/producao
```

`SecretReference` permanece na configuração, serialização e fingerprint.
Somente a factory ou ativação de plugin recebe acesso ao `SecretResolver`
injetado. `SecretValue` mascara `str()` e `repr()`, mas seu valor ainda é
sensível e deve existir pelo menor tempo possível.

`MappingSecretResolver` é útil em testes ou quando o host já consultou um cofre.
O padrão `RejectingSecretResolver` falha fechado. O pacote não oferece leitura
implícita de variáveis de ambiente; um host que precise disso deve implementar
`SecretResolver` e controlar allowlist, auditoria e lifecycle.
