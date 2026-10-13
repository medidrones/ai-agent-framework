# HITL durável em Kubernetes

Ambiente: kind com Kubernetes 1.31.2 e Calico 3.31.7. A imagem instala wheels,
roda non-root, usa filesystem raiz somente leitura, não monta token de
ServiceAccount e recebe credenciais por Secret.

Cenários executados:

- aprovação PostgreSQL depois de substituição de pod;
- rejeição Redis durante rolling update;
- escala para dez workers;
- 50 suspensões pendentes preservadas;
- 100 resumes concorrentes entre pods;
- regressão integral DS-013, incluindo probes, shutdown, backend restart,
  fencing, rede, cancellation e deadlines.

O cluster kind possui um nó e não certifica falha física multi-node.
