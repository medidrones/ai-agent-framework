# Scripts Lua

Os scripts ficam versionados em `redis/scripts.py` e nunca são construídos a
partir de entrada externa. Chaves e argumentos trafegam somente por `KEYS` e
`ARGV`. Não há carregamento no import, comando administrativo ou interpolação
de payload em código.

Scripts adicionados pela DS-011:

- aquisição, renovação e liberação de lease;
- compare-and-swap protegido por fencing;
- consumo autorizado protegido por fencing;
- reconciliação por identificador de operação.

A matriz certificada é Redis 7.4.11 standalone. Redis Functions não foram
necessárias; os scripts de chave única fornecem o ponto atômico exigido.
