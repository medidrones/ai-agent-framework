# Consumo atômico

O script de consumo valida schema, estado e expiração, captura o payload, muda o
estado para `consumed`, grava receipt interno, remove payload/digest e aplica o
TTL do tombstone em uma única execução Redis.

Em `consume_authorized`, a decisão síncrona ocorre sobre um snapshot validado;
o script consome somente se revisão e digest ainda coincidirem. Uma decisão
inválida não inicia a mutação. Vinte consumidores reais simultâneos produziram
um sucesso e dezenove rejeições.

O receipt permite distinguir, após uma falha de resposta, que o comando foi
aplicado. Como o payload já foi removido, o adapter retorna resultado tipado
desconhecido e nunca presume rollback ou repete o efeito.
