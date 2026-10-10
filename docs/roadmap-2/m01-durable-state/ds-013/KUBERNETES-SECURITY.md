# Segurança Kubernetes

O worker executa como UID/GID 10001, sem privilege escalation, com todas as
capabilities removidas, filesystem raiz read-only, seccomp RuntimeDefault,
limites de CPU/memória e sem automount do token. Não usa privileged, hostPath,
hostNetwork ou Docker socket.

RBAC negou create deployment, delete pod, update secret, create clusterrole e
update namespace. Segredos efêmeros são gerados em memória e injetados por
Secret; a busca em logs e metadata da imagem não encontrou os valores.

Init containers usam root apenas para ownership de PVC, com capabilities
limitadas a `CHOWN`, `DAC_OVERRIDE` e `FOWNER`; processos de runtime são
non-root. Nenhum scanner de imagem (`trivy`, `grype`, `dockle`) estava instalado,
portanto esse controle opcional não foi executado.
