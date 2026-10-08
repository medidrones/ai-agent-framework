# Proteção contra replay

O token é derivado para uma chave opaca e nunca armazenado em claro. O primeiro
consumo transforma o registro em tombstone e elimina o payload. Um novo consumo,
um segundo resume ou a reutilização do token recebe rejeição controlada.

O tombstone permanece até `consumed_retention`; salvar novamente sob a mesma
chave também é recusado. Namespace e digest do token impedem consumo cruzado.
A garantia termina após a janela de retenção contratada e depende de política
`noeviction` para não haver remoção antecipada pelo deployment.
