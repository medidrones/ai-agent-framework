# Semântica temporal

Datas são `TIMESTAMPTZ` e modelos exigem timezone. O relógio da aplicação pode
calcular candidatos de prazo, mas decisões de validade e a fotografia
`evaluated_at` usam o PostgreSQL. A fronteira é inclusiva para expiração e para
fim de retenção. Não há dependência de relógio local sincronizado entre workers.
