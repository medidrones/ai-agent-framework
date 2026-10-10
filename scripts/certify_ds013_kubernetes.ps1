[CmdletBinding()]
param(
    [switch]$KeepNamespace
)

$ErrorActionPreference = 'Stop'
$context = 'kind-atlas-ds013'
$namespace = 'atlas-ds013'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:kubectlExecutable = Join-Path $root 'build/ds013/kubectl-v1.31.2.exe'
if (-not (Test-Path -LiteralPath $script:kubectlExecutable)) {
    throw 'Execute scripts/prepare_ds013_cluster.ps1 para provisionar o kubectl v1.31.2 verificado.'
}
Set-Alias -Name kubectl -Value $script:kubectlExecutable -Scope Script
$example = Join-Path $root 'examples/kubernetes-recovery'
$evidence = Join-Path $root 'build/ds013/evidence'
$kindCandidate = Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Packages/Kubernetes.kind_Microsoft.Winget.Source_8wekyb3d8bbwe/kind.exe'
$kindCommand = Get-Command kind -ErrorAction SilentlyContinue
$kind = if ($null -ne $kindCommand) { $kindCommand.Source } elseif (Test-Path -LiteralPath $kindCandidate) { $kindCandidate } else { throw 'kind não foi encontrado.' }

function Assert-ExitCode([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

function Invoke-Runner([string]$Method, [string]$Path) {
    $value = kubectl --context $context -n $namespace exec ds013-runner -- atlas-kubernetes-client $Method $Path
    Assert-ExitCode "Falha ao invocar $Method $Path."
    return ($value -join "`n")
}

function Wait-Result([string]$ExecutionId, [string]$Expected, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $status = Invoke-Runner 'GET' '/status'
        if ($status -match [regex]::Escape($ExecutionId) -and $status -match [regex]::Escape($Expected)) {
            return $status
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    throw "Resultado $Expected não observado para $ExecutionId."
}

function Assert-Equal([object]$Actual, [object]$Expected, [string]$Message) {
    if ($Actual -ne $Expected) {
        throw "$Message Esperado: $Expected; obtido: $Actual."
    }
}

function Assert-Match([string]$Actual, [string]$Pattern, [string]$Message) {
    if ($Actual -notmatch $Pattern) { throw $Message }
}

function Get-WorkerRestartCount {
    $payload = kubectl --context $context -n $namespace get pods `
        -l app.kubernetes.io/name=atlas-worker -o json | ConvertFrom-Json
    Assert-ExitCode 'Falha ao obter os restart counts dos workers.'
    $counts = $payload.items | Sort-Object { $_.metadata.name } | ForEach-Object {
        "$($_.metadata.name)=$($_.status.containerStatuses[0].restartCount)"
    }
    return ($counts -join "`n").Trim()
}

function Get-EffectCount([string]$ExecutionId) {
    $command = 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --raw GET "atlas:ds013:effect-count:' + $ExecutionId + '"'
    $value = kubectl --context $context -n $namespace exec deployment/redis -- sh -c $command
    Assert-ExitCode "Falha ao consultar o efeito de $ExecutionId."
    $normalized = ($value -join '').Trim()
    if (-not $normalized) { return 0 }
    return [int]$normalized
}

function Assert-NoResult([string]$ExecutionId, [int]$WaitSeconds = 3) {
    Start-Sleep -Seconds $WaitSeconds
    $status = Invoke-Runner 'GET' '/status'
    if ($status -match [regex]::Escape($ExecutionId)) {
        throw "A execução $ExecutionId produziu resultado quando deveria permanecer suspensa."
    }
}

function Measure-Scenario([string]$Name, [scriptblock]$Action) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    & $Action
    $watch.Stop()
    $script:performance[$Name] = [Math]::Round($watch.Elapsed.TotalMilliseconds, 3)
}

function New-HexSecret([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    }
    finally {
        $generator.Dispose()
    }
    return ([BitConverter]::ToString($buffer) -replace '-', '').ToLowerInvariant()
}

$expectedEvidenceRoot = Join-Path $root 'build/ds013/evidence'
if ([IO.Path]::GetFullPath($evidence) -ne [IO.Path]::GetFullPath($expectedEvidenceRoot)) {
    throw 'O diretório de evidências resolvido não é o esperado.'
}
if (Test-Path -LiteralPath $evidence) {
    Get-ChildItem -LiteralPath $evidence -Force | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$performance = [ordered]@{}
$transcript = Join-Path $evidence 'certification-transcript.txt'
Start-Transcript -LiteralPath $transcript -Force | Out-Null

try {
    $currentContext = kubectl config current-context
    if ($currentContext -ne $context) {
        throw "Contexto Kubernetes inesperado: $currentContext"
    }

    docker build --file (Join-Path $example 'Dockerfile') --tag atlas-ds013:1.0.1 $root
    Assert-ExitCode 'Falha ao construir a imagem de certificação.'
    & $kind load docker-image atlas-ds013:1.0.1 --name atlas-ds013
    Assert-ExitCode 'Falha ao carregar a imagem no kind.'

    $existingNamespace = kubectl --context $context get namespace $namespace --ignore-not-found -o name
    Assert-ExitCode 'Falha ao verificar o namespace de certificação.'
    if (($existingNamespace -join '').Trim()) {
        if ($namespace -ne 'atlas-ds013') { throw 'O namespace de limpeza não é o esperado.' }
        kubectl --context $context delete namespace $namespace --wait=true --timeout=180s
        Assert-ExitCode 'Falha ao limpar o namespace da certificação anterior.'
    }

    kubectl --context $context apply -f (Join-Path $example 'k8s/namespace.yaml')
    $postgresUser = 'atlas_' + (New-HexSecret 4)
    $postgresPassword = New-HexSecret 24
    $redisPassword = New-HexSecret 24
    $hmacKey = New-HexSecret 32
    $postgresDsn = "postgresql://$postgresUser`:$postgresPassword@postgresql:5432/atlas"
    $redisUrl = "redis://`:$redisPassword@redis:6379/0"
    $secret = kubectl --context $context -n $namespace create secret generic atlas-ds013-credentials `
        --from-literal=postgresql-user=$postgresUser `
        --from-literal=postgresql-password=$postgresPassword `
        --from-literal=postgresql-dsn=$postgresDsn `
        --from-literal=redis-password=$redisPassword `
        --from-literal=redis-url=$redisUrl `
        --from-literal=token-hmac-key=$hmacKey `
        --dry-run=client -o json
    $secret | & $script:kubectlExecutable --context $context apply -f - | Out-Null
    Assert-ExitCode 'Falha ao criar o Secret efêmero de teste.'

    foreach ($manifest in @(
        'serviceaccount.yaml', 'configmap.yaml', 'storage.yaml',
        'postgresql.yaml', 'redis.yaml', 'networkpolicy.yaml',
        'deployment.yaml', 'poddisruptionbudget.yaml'
    )) {
        kubectl --context $context apply -f (Join-Path $example "k8s/$manifest")
        Assert-ExitCode "Falha ao aplicar $manifest."
    }

    kubectl --context $context -n $namespace rollout status deployment/postgresql --timeout=180s
    kubectl --context $context -n $namespace rollout status deployment/redis --timeout=180s
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=240s
    Assert-ExitCode 'Os deployments não ficaram disponíveis.'

    kubectl --context $context -n $namespace delete pod ds013-runner --ignore-not-found --wait=true | Out-Null
    kubectl --context $context -n $namespace run ds013-runner `
        --image=atlas-ds013:1.0.1 --image-pull-policy=Never --restart=Never `
        --labels='atlas.medicode.dev/certification-runner=true' `
        --command -- sleep 3600
    kubectl --context $context -n $namespace wait pod/ds013-runner --for=condition=Ready --timeout=120s
    Assert-ExitCode 'O runner de certificação não ficou pronto.'

    Invoke-Runner 'GET' '/ready' | Out-File (Join-Path $evidence 'initial-readiness.json') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-pod-crash&decision=pending' | Out-Null
    $pod = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    kubectl --context $context -n $namespace delete pod $pod --wait=true
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-pod-crash&decision=approve' | Out-Null
    Wait-Result 'postgresql-pod-crash' 'recovered' | Out-File (Join-Path $evidence 'postgresql-pod-crash.json') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=redis&execution_id=redis-pod-crash&decision=pending' | Out-Null
    $pod = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    kubectl --context $context -n $namespace delete pod $pod --wait=true
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    Invoke-Runner 'POST' '/decide?execution_id=redis-pod-crash&decision=approve' | Out-Null
    Wait-Result 'redis-pod-crash' 'completed' | Out-File (Join-Path $evidence 'redis-pod-crash.json') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-rejected&decision=reject' | Out-Null
    Wait-Result 'postgresql-rejected' 'rejected' | Out-File (Join-Path $evidence 'postgresql-rejected.json') -Encoding utf8

    kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=3
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-concurrent&decision=approve' | Out-Null
    Wait-Result 'postgresql-concurrent' 'recovered' | Out-File (Join-Path $evidence 'postgresql-concurrent.json') -Encoding utf8
    Invoke-Runner 'POST' '/seed?backend=redis&execution_id=redis-concurrent&decision=approve' | Out-Null
    Wait-Result 'redis-concurrent' 'completed' | Out-File (Join-Path $evidence 'redis-concurrent.json') -Encoding utf8

    kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=1
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=2
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s

    kubectl --context $context -n $namespace rollout restart deployment/atlas-worker
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    Assert-ExitCode 'Rolling restart falhou.'

    $before = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o json
    kubectl --context $context -n $namespace scale deployment/postgresql --replicas=0
    Start-Sleep -Seconds 5
    $during = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o json
    kubectl --context $context -n $namespace scale deployment/postgresql --replicas=1
    kubectl --context $context -n $namespace rollout status deployment/postgresql --timeout=180s
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    $before | Out-File (Join-Path $evidence 'pods-before-postgresql-loss.json') -Encoding utf8
    $during | Out-File (Join-Path $evidence 'pods-during-postgresql-loss.json') -Encoding utf8

    Assert-Equal (Get-EffectCount 'postgresql-pod-crash') 1 'O recovery PostgreSQL repetiu ou perdeu o efeito.'
    Assert-Equal (Get-EffectCount 'redis-pod-crash') 1 'O recovery Redis repetiu ou perdeu o efeito.'
    Assert-Equal (Get-EffectCount 'postgresql-concurrent') 1 'O recovery concorrente PostgreSQL não foi único.'
    Assert-Equal (Get-EffectCount 'redis-concurrent') 1 'O recovery concorrente Redis não foi único.'
    Assert-Equal (Get-EffectCount 'postgresql-rejected') 0 'A rejeição HITL executou um efeito externo.'

    Invoke-Runner 'POST' '/decide?execution_id=postgresql-pod-crash&decision=approve' | Out-Null
    Start-Sleep -Seconds 2
    Assert-Equal (Get-EffectCount 'postgresql-pod-crash') 1 'O checkpoint PostgreSQL consumido foi reproduzido.'

    $deadline = Invoke-Runner 'POST' '/runtime-control?mode=deadline'
    Assert-Match $deadline '"status": "timed_out"' 'O deadline absoluto não foi preservado.'
    $deadline | Out-File (Join-Path $evidence 'runtime-deadline.json') -Encoding utf8
    $cancellation = Invoke-Runner 'POST' '/runtime-control?mode=cancellation'
    Assert-Match $cancellation '"status": "cancelled"' 'O cancelamento do consumidor não foi propagado.'
    $cancellation | Out-File (Join-Path $evidence 'runtime-cancellation.json') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-backend-restart&decision=pending' | Out-Null
    $restartsBeforePostgresql = Get-WorkerRestartCount
    Measure-Scenario 'postgresql_restart_ms' {
        kubectl --context $context -n $namespace delete pod -l app.kubernetes.io/name=postgresql --wait=true
        kubectl --context $context -n $namespace rollout status deployment/postgresql --timeout=180s
        Assert-ExitCode 'O PostgreSQL não se recuperou após o restart.'
    }
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-backend-restart&decision=approve' | Out-Null
    Wait-Result 'postgresql-backend-restart' 'recovered' | Out-File (Join-Path $evidence 'postgresql-backend-restart.json') -Encoding utf8
    Assert-Equal (Get-EffectCount 'postgresql-backend-restart') 1 'O checkpoint não sobreviveu ao restart do PostgreSQL.'
    Assert-Equal (Get-WorkerRestartCount) $restartsBeforePostgresql 'A indisponibilidade do PostgreSQL causou restart loop dos workers.'

    Invoke-Runner 'POST' '/seed?backend=redis&execution_id=redis-backend-restart&decision=pending' | Out-Null
    $restartsBeforeRedis = Get-WorkerRestartCount
    Measure-Scenario 'redis_restart_ms' {
        kubectl --context $context -n $namespace delete pod -l app.kubernetes.io/name=redis --wait=true
        kubectl --context $context -n $namespace rollout status deployment/redis --timeout=180s
        Assert-ExitCode 'O Redis não se recuperou após o restart.'
    }
    Invoke-Runner 'POST' '/decide?execution_id=redis-backend-restart&decision=approve' | Out-Null
    Wait-Result 'redis-backend-restart' 'completed' | Out-File (Join-Path $evidence 'redis-backend-restart.json') -Encoding utf8
    Assert-Equal (Get-EffectCount 'redis-backend-restart') 1 'O checkpoint não sobreviveu ao restart Redis/AOF.'
    Assert-Equal (Get-WorkerRestartCount) $restartsBeforeRedis 'A indisponibilidade do Redis causou restart loop dos workers.'

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-graceful&decision=pending' | Out-Null
    $gracefulPod = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    Measure-Scenario 'graceful_shutdown_ms' {
        kubectl --context $context -n $namespace delete pod $gracefulPod --grace-period=20 --wait=true
        kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
        Assert-ExitCode 'O replacement após SIGTERM não ficou disponível.'
    }
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-graceful&decision=approve' | Out-Null
    Wait-Result 'postgresql-graceful' 'recovered' | Out-File (Join-Path $evidence 'graceful-shutdown-recovery.json') -Encoding utf8
    $auditPod = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    $shutdownAudit = kubectl --context $context -n $namespace exec $auditPod -- sh -c 'grep -h atlas.worker.shutdown /var/lib/atlas/approvals/lifecycle-*.jsonl'
    Assert-ExitCode 'O evento de graceful shutdown não foi preservado.'
    $shutdownAudit | Out-File (Join-Path $evidence 'graceful-shutdown-events.jsonl') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-container-restart&decision=pending' | Out-Null
    $containerPod = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    $podUidBefore = kubectl --context $context -n $namespace get pod $containerPod -o jsonpath='{.metadata.uid}'
    $restartBefore = [int](kubectl --context $context -n $namespace get pod $containerPod -o jsonpath='{.status.containerStatuses[0].restartCount}')
    kubectl --context $context -n $namespace exec $containerPod -- sh -c 'kill -TERM 1'
    Start-Sleep -Seconds 3
    kubectl --context $context -n $namespace wait pod/$containerPod --for=condition=Ready --timeout=180s
    Assert-ExitCode 'O container não reiniciou no mesmo pod.'
    $podUidAfter = kubectl --context $context -n $namespace get pod $containerPod -o jsonpath='{.metadata.uid}'
    $restartAfter = [int](kubectl --context $context -n $namespace get pod $containerPod -o jsonpath='{.status.containerStatuses[0].restartCount}')
    Assert-Equal $podUidAfter $podUidBefore 'O teste deveria reiniciar o container sem substituir o pod.'
    if ($restartAfter -le $restartBefore) { throw 'O restartCount do container não avançou.' }
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-container-restart&decision=approve' | Out-Null
    Wait-Result 'postgresql-container-restart' 'recovered' | Out-File (Join-Path $evidence 'container-restart.json') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-crash-after-effect&decision=pending' | Out-Null
    Invoke-Runner 'POST' '/arm-crash-after-effect?execution_id=postgresql-crash-after-effect' | Out-Null
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-crash-after-effect&decision=approve' | Out-Null
    Wait-Result 'postgresql-crash-after-effect' 'recovered' 120 | Out-File (Join-Path $evidence 'crash-after-effect.json') -Encoding utf8
    Assert-Equal (Get-EffectCount 'postgresql-crash-after-effect') 1 'O resultado desconhecido repetiu o efeito externo.'

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=tenant-isolation&decision=approve&tenant_id=tenant-other' | Out-Null
    Assert-NoResult 'tenant-isolation' 4
    $tenantAttempts = kubectl --context $context -n $namespace exec deployment/postgresql -- `
        psql -U $postgresUser -d atlas -At -c `
        "SELECT count(*) FROM atlas_agent.execution_recovery_attempts WHERE execution_id = 'tenant-isolation';"
    Assert-ExitCode 'Falha ao consultar tentativas do cenário de isolamento.'
    Assert-Equal (($tenantAttempts -join '').Trim()) '0' 'O coordinator recuperou checkpoint de outro tenant.'
    $tenantAttempts | Out-File (Join-Path $evidence 'tenant-isolation.txt') -Encoding utf8

    $redisPolicy = kubectl --context $context -n $namespace exec deployment/redis -- sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --raw CONFIG GET maxmemory-policy'
    Assert-Match ($redisPolicy -join "`n") 'noeviction' 'O Redis não está configurado para detectar pressão sem eviction silenciosa.'
    $redisPolicy | Out-File (Join-Path $evidence 'redis-eviction-policy.txt') -Encoding utf8

    kubectl --context $context -n $namespace exec deployment/redis -- sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli CONFIG SET maxmemory 1' | Out-Null
    Assert-ExitCode 'Falha ao aplicar pressão de memória controlada no Redis.'
    $evictionPressure = kubectl --context $context -n $namespace exec deployment/redis -- sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli SET ds013-eviction-probe blocked'
    kubectl --context $context -n $namespace exec deployment/redis -- sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli CONFIG SET maxmemory 0' | Out-Null
    Assert-ExitCode 'Falha ao restaurar o limite de memória do Redis.'
    Assert-Match ($evictionPressure -join "`n") 'OOM' 'A política noeviction não rejeitou a escrita sob pressão.'
    $evictionPressure | Out-File (Join-Path $evidence 'redis-eviction-pressure.txt') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-network-partition&decision=pending' | Out-Null
    Invoke-Runner 'POST' '/arm-delay-after-effect?execution_id=postgresql-network-partition&seconds=8' | Out-Null
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-network-partition&decision=approve' | Out-Null
    Start-Sleep -Seconds 1
    $partitionPolicy = kubectl --context $context -n $namespace get networkpolicy atlas-worker-restricted -o json | ConvertFrom-Json
    $partitionPolicy.spec.egress = @($partitionPolicy.spec.egress[0], $partitionPolicy.spec.egress[2])
    $partitionPolicy | ConvertTo-Json -Depth 100 | & $script:kubectlExecutable --context $context replace -f - | Out-Null
    Assert-ExitCode 'Falha ao aplicar a partição PostgreSQL controlada.'
    Start-Sleep -Seconds 8
    kubectl --context $context apply -f (Join-Path $example 'k8s/networkpolicy.yaml') | Out-Null
    Assert-ExitCode 'Falha ao restaurar a política de rede.'
    Wait-Result 'postgresql-network-partition' 'recovered' 120 | Out-File (Join-Path $evidence 'network-partition-recovery.json') -Encoding utf8
    Assert-Equal (Get-EffectCount 'postgresql-network-partition') 1 'A partição durante lease repetiu o efeito.'

    $dnsPolicy = kubectl --context $context -n $namespace get networkpolicy atlas-worker-restricted -o json | ConvertFrom-Json
    $dnsPolicy.spec.egress = @($dnsPolicy.spec.egress[1], $dnsPolicy.spec.egress[2])
    $dnsPolicy | ConvertTo-Json -Depth 100 | & $script:kubectlExecutable --context $context replace -f - | Out-Null
    Assert-ExitCode 'Falha ao aplicar a perda controlada de DNS.'
    kubectl --context $context -n $namespace delete pod `
        -l app.kubernetes.io/name=atlas-worker --wait=true | Out-Null
    Assert-ExitCode 'Falha ao substituir os workers durante a perda de DNS.'
    Start-Sleep -Seconds 8
    $readyDuringDnsLoss = kubectl --context $context -n $namespace get deployment atlas-worker -o jsonpath='{.status.readyReplicas}'
    Assert-ExitCode 'Falha ao consultar a disponibilidade durante a perda de DNS.'
    $readyReplicaCount = if (($readyDuringDnsLoss -join '').Trim()) { [int](($readyDuringDnsLoss -join '').Trim()) } else { 0 }
    Assert-Equal $readyReplicaCount 0 'A perda de DNS não tornou os novos workers indisponíveis como esperado.'
    kubectl --context $context apply -f (Join-Path $example 'k8s/networkpolicy.yaml') | Out-Null
    Assert-ExitCode 'Falha ao restaurar DNS na NetworkPolicy.'
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s | Out-Null
    Assert-ExitCode 'O worker não se recuperou após restaurar DNS.'
    "readyReplicas=$readyReplicaCount" | Out-File (Join-Path $evidence 'dns-loss-readiness.txt') -Encoding utf8

    Invoke-Runner 'POST' '/seed?backend=postgresql&execution_id=postgresql-grace-expired&decision=pending' | Out-Null
    $forcedPod = kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    kubectl --context $context -n $namespace delete pod $forcedPod --grace-period=0 --force --wait=true | Out-Null
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s | Out-Null
    Assert-ExitCode 'O replacement após grace period zero não ficou disponível.'
    Invoke-Runner 'POST' '/decide?execution_id=postgresql-grace-expired&decision=approve' | Out-Null
    Wait-Result 'postgresql-grace-expired' 'recovered' | Out-File (Join-Path $evidence 'grace-period-expired.json') -Encoding utf8
    Assert-Equal (Get-EffectCount 'postgresql-grace-expired') 1 'O término forçado repetiu ou perdeu o efeito.'

    kubectl --context $context -n $namespace delete pod ds013-denied --ignore-not-found --wait=true | Out-Null
    kubectl --context $context -n $namespace run ds013-denied `
        --image=atlas-ds013:1.0.1 --image-pull-policy=Never --restart=Never `
        --command -- sleep 3600
    kubectl --context $context -n $namespace wait pod/ds013-denied --for=condition=Ready --timeout=120s
    Assert-ExitCode 'O pod não autorizado de teste não ficou pronto.'
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $deniedOutput = kubectl --context $context -n $namespace exec ds013-denied -- atlas-kubernetes-client GET /live 2>&1
    $deniedExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorPreference
    if ($deniedExitCode -eq 0) { throw 'A NetworkPolicy permitiu acesso de um pod não autorizado.' }
    $deniedOutput | Out-File (Join-Path $evidence 'networkpolicy-denied.txt') -Encoding utf8
    Invoke-Runner 'GET' '/live' | Out-File (Join-Path $evidence 'networkpolicy-allowed.json') -Encoding utf8

    $attemptEvidence = kubectl --context $context -n $namespace exec deployment/postgresql -- `
        psql -U $postgresUser -d atlas -At -F ',' -c `
        "SELECT execution_id, attempt_number, outcome, COALESCE(reason_code, ''), owner_id, fencing_token FROM atlas_agent.execution_recovery_attempts ORDER BY started_at;"
    Assert-ExitCode 'Falha ao consultar ownership e fencing.'
    $attemptEvidence | Out-File (Join-Path $evidence 'recovery-attempts.csv') -Encoding utf8

    $effectEvidence = [ordered]@{}
    foreach ($executionId in @(
        'postgresql-pod-crash', 'redis-pod-crash', 'postgresql-concurrent',
        'redis-concurrent', 'postgresql-rejected', 'postgresql-backend-restart',
        'redis-backend-restart', 'postgresql-graceful', 'postgresql-container-restart',
        'postgresql-crash-after-effect', 'postgresql-network-partition',
        'postgresql-grace-expired'
    )) {
        $effectEvidence[$executionId] = Get-EffectCount $executionId
    }
    $effectEvidence | ConvertTo-Json | Out-File (Join-Path $evidence 'external-effects.json') -Encoding utf8
    $performance | ConvertTo-Json | Out-File (Join-Path $evidence 'performance.json') -Encoding utf8

    $rbacChecks = @(
        @{ Verb = 'create'; Resource = 'deployments'; Namespaced = $true },
        @{ Verb = 'delete'; Resource = 'pods'; Namespaced = $true },
        @{ Verb = 'update'; Resource = 'secrets'; Namespaced = $true },
        @{ Verb = 'create'; Resource = 'clusterroles.rbac.authorization.k8s.io'; Namespaced = $false },
        @{ Verb = 'update'; Resource = 'namespaces'; Namespaced = $false }
    )
    $rbacEvidence = @()
    foreach ($check in $rbacChecks) {
        $previousErrorPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        if ($check.Namespaced) {
            $answer = kubectl --context $context -n $namespace auth can-i $check.Verb $check.Resource --as=system:serviceaccount:$namespace`:atlas-worker 2>$null
        }
        else {
            $answer = kubectl --context $context auth can-i $check.Verb $check.Resource `
                --all-namespaces --as=system:serviceaccount:$namespace`:atlas-worker 2>$null
        }
        $ErrorActionPreference = $previousErrorPreference
        $operation = "$($check.Verb) $($check.Resource)"
        Assert-Equal (($answer -join '').Trim()) 'no' "A ServiceAccount possui permissão excessiva para $operation."
        $rbacEvidence += "$operation=no"
    }
    $rbacEvidence | Out-File (Join-Path $evidence 'worker-rbac.txt') -Encoding utf8
    kubectl --context $context -n $namespace get deployment,serviceaccount,networkpolicy,poddisruptionbudget -o yaml | Out-File (Join-Path $evidence 'applied-security.yaml') -Encoding utf8
    kubectl --context $context -n $namespace get events --sort-by=.metadata.creationTimestamp | Out-File (Join-Path $evidence 'events.txt') -Encoding utf8
    $workerLogs = kubectl --context $context -n $namespace logs -l app.kubernetes.io/name=atlas-worker --all-containers=true --prefix=true
    $workerLogs | Out-File (Join-Path $evidence 'worker-logs.txt') -Encoding utf8
    $imageInspect = docker image inspect atlas-ds013:1.0.1
    $imageInspect | Out-File (Join-Path $evidence 'image-inspect.json') -Encoding utf8
    $sensitiveEvidence = (($workerLogs -join "`n") + "`n" + ($imageInspect -join "`n"))
    foreach ($secretValue in @($postgresPassword, $redisPassword, $hmacKey)) {
        if ($sensitiveEvidence.Contains($secretValue)) {
            throw 'Uma credencial efêmera foi encontrada em logs ou metadados da imagem.'
        }
    }
    $workerDeployment = kubectl --context $context -n $namespace get deployment atlas-worker -o json | ConvertFrom-Json
    $podSpec = $workerDeployment.spec.template.spec
    $workerSecurity = $podSpec.containers[0].securityContext
    Assert-Equal $podSpec.automountServiceAccountToken $false 'O token da ServiceAccount foi montado.'
    Assert-Equal $podSpec.securityContext.runAsNonRoot $true 'O pod worker não exige execução non-root.'
    Assert-Equal $workerSecurity.allowPrivilegeEscalation $false 'Privilege escalation não foi desabilitada.'
    Assert-Equal $workerSecurity.readOnlyRootFilesystem $true 'O filesystem do worker não é read-only.'
    Assert-Equal $workerSecurity.privileged $null 'O worker declarou privileged.'
    Assert-Equal $podSpec.hostNetwork $null 'O worker declarou hostNetwork.'
    if ($podSpec.volumes | Where-Object { $null -ne $_.hostPath }) {
        throw 'O worker utiliza hostPath sem autorização.'
    }
    kubectl --context $context version -o yaml | Out-File (Join-Path $evidence 'kubernetes-version.yaml') -Encoding utf8
}
finally {
    Stop-Transcript | Out-Null
    if (-not $KeepNamespace) {
        if ($namespace -ne 'atlas-ds013') { throw 'O namespace de cleanup não é o esperado.' }
        kubectl --context $context delete namespace $namespace --wait=true --timeout=180s
    }
}
