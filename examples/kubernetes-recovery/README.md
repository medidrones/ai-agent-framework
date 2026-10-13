# Recuperação do Atlas em Kubernetes

Host técnico usado para certificar lifecycle de pods, recovery distribuído,
PostgreSQL, Redis e HITL durável no `kind`. Não é uma aplicação de negócio nem
um sistema de autenticação ou uma interface de aprovação.

## Pré-requisitos

- Docker Desktop;
- PowerShell 5.1 ou superior;
- `kind` v0.33.0;
- acesso à internet apenas na preparação inicial das imagens e do Calico.

O script de preparação baixa e verifica o `kubectl` v1.31.2, cria um cluster
Kubernetes v1.31.2 e instala Calico v3.31.7:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_ds013_cluster.ps1 -Recreate
```

Execute a certificação e o benchmark a partir da raiz:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/certify_ds013_kubernetes.ps1 -KeepNamespace
powershell -ExecutionPolicy Bypass -File scripts/benchmark_ds013_kubernetes.ps1
powershell -ExecutionPolicy Bypass -File scripts/certify_ds014_durable_hitl.ps1
```

Use `-KeepNamespace` na certificação somente para inspeção. Sem essa opção, o
namespace `atlas-ds013` é removido depois que as evidências locais são salvas em
`build/ds013/evidence/`.

A certificação DS-014 reutiliza o cluster e o namespace preservado pela
DS-013, executa os fluxos PostgreSQL/Redis, restarts, rolling update, dez
workers e as cargas obrigatórias. Suas evidências locais ficam em
`build/ds014/evidence/`. O token de retomada trafega somente no corpo JSON e
não é incluído em URL, log, auditoria ou tabela de aprovação.

O boundary recebe uma identidade que já foi autenticada pelo host. Em produção,
a aplicação deve integrar seu IdP e construir `TrustedApprovalPrincipal` apenas
com claims verificadas.

As credenciais são aleatórias e efêmeras. O worker usa fake provider e fake
tool; nenhuma chave de provedor externo é necessária.
