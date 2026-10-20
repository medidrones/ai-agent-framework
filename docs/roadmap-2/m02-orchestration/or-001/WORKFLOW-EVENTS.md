# Eventos de workflow

Eventos carregam identidades do evento e da execução, tipo, timestamp com fuso,
correlação, nó opcional, payload JSON imutável e versão de schema.

Eles representam fatos funcionais como criação, início, scheduling, execução e
conclusão de nós, espera, retomada e encerramento. Não substituem spans,
métricas ou logs e não pressupõem event bus distribuído.
