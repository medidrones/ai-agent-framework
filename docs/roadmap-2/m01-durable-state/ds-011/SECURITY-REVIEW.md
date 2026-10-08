# Revisão de segurança

- token e namespace aparecem apenas como digests na chave;
- credencial, URL, token e payload não aparecem em mensagens de erro;
- autorização não é derivada de checkpoint ID ou metadata;
- scripts são estáticos e recebem somente `KEYS`/`ARGV`;
- tenant e identidades persistidas são validados;
- operation ID e owner possuem validação de tamanho/formato;
- Redis continua dependência opcional fora do core;
- não há retry automático, lock global ou execução antecipada de ferramenta.

Bandit terminou sem findings. `pip-audit` do ambiente clean-install terminou sem
vulnerabilidades conhecidas. Não há finding CRITICAL/HIGH aberto.
