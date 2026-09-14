# Política de depreciação

Uma API pública estável permanece depreciada por pelo menos dois releases
minor antes da remoção. O changelog registra:

- release que iniciou a depreciação;
- substituição recomendada;
- primeira versão em que a remoção poderá ocorrer.

APIs consumidas diretamente devem emitir `AtlasDeprecationWarning`, derivada
de `FutureWarning`, uma vez na fronteira pública. Warnings não devem ser
emitidos em loops internos.

APIs explicitamente experimentais não recebem essa garantia. Correções de
segurança podem desabilitar ou remover imediatamente um comportamento inseguro
e podem elevar pisos de dependências em PATCH; a exceção deve ser explicada no
changelog e no aviso de segurança.
