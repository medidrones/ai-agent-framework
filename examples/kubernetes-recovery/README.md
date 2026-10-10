# Recuperação do Atlas em Kubernetes

Host técnico usado para certificar lifecycle de pods, recovery distribuído,
PostgreSQL, Redis e HITL no `kind`. Não é uma aplicação de negócio.

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
powershell -ExecutionPolicy Bypass -File scripts/certify_ds013_kubernetes.ps1
powershell -ExecutionPolicy Bypass -File scripts/benchmark_ds013_kubernetes.ps1
```

Use `-KeepNamespace` na certificação somente para inspeção. Sem essa opção, o
namespace `atlas-ds013` é removido depois que as evidências locais são salvas em
`build/ds013/evidence/`.

As credenciais são aleatórias e efêmeras. O worker usa fake provider e fake
tool; nenhuma chave de provedor externo é necessária.
