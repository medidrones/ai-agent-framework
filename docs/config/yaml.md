# YAML, JSON e objetos Python

`load_yaml(texto)`, `load_json(texto)` e `load_config(caminho)` produzem o mesmo
modelo canônico. `load_config` aceita `.yaml`, `.yml` e `.json`, sempre em
UTF-8. Também é possível chamar `AtlasConfig.model_validate(objeto)` quando a
aplicação já possui dados Python confiáveis.

O YAML usa um loader seguro e rejeita tags Python, chaves duplicadas e raiz que
não seja mapping. JSON também rejeita chaves duplicadas. Não há includes,
import dinâmico, interpolação de ambiente, busca remota, `eval` ou `exec`.

Para validação sem composição, use:

```python
from atlas_agents.config import validate_config_file

resultado = validate_config_file("atlas.yaml")
if not resultado.valid:
    for erro in resultado.errors:
        print(erro.code, erro.path, erro.message)
```

Mensagens retornadas são seguras para apresentação; exceções internas de
factories não são incorporadas à mensagem pública.
