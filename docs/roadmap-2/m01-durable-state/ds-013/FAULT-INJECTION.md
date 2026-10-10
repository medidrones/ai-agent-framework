# Fault injection

`scripts/certify_ds013_kubernetes.ps1` reproduz pod kill, container restart,
scale, rollout, disconnect/restart dos backends, recovery concorrente e crash
após efeito. `scripts/benchmark_ds013_kubernetes.ps1` mede os caminhos críticos.

Os scripts validam o contexto `kind-atlas-ds013`, operam somente no namespace
`atlas-ds013` e removem esse namespace por padrão. Não devem ser usados contra
produção. `-KeepNamespace` serve exclusivamente para inspeção local.
