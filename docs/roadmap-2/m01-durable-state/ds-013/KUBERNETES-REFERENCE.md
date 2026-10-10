# Referência Kubernetes

Ambiente certificado: `kind` v0.33.0, Kubernetes cliente/servidor v1.31.2,
Calico v3.31.7, um nó control-plane, containerd 1.7.24 e Docker Desktop 29.8.1.

Os manifests ficam em `examples/kubernetes-recovery/k8s/` e incluem namespace,
ServiceAccount, ConfigMap, PVCs, PostgreSQL, Redis, worker Deployment, PDB e
NetworkPolicies. As imagens de base e dos bancos estão presas por digest.

O script `scripts/prepare_ds013_cluster.ps1` verifica checksums do Calico e do
`kubectl`. `scripts/certify_ds013_kubernetes.ps1` cria somente recursos do
namespace `atlas-ds013`, salva evidências e faz cleanup por padrão.
