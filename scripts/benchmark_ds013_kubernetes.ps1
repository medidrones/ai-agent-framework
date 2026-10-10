[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$context = 'kind-atlas-ds013'
$namespace = 'atlas-ds013'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:kubectlExecutable = Join-Path $root 'build/ds013/kubectl-v1.31.2.exe'
if (-not (Test-Path -LiteralPath $script:kubectlExecutable)) {
    throw 'Execute scripts/prepare_ds013_cluster.ps1 para provisionar o kubectl v1.31.2 verificado.'
}
Set-Alias -Name kubectl -Value $script:kubectlExecutable -Scope Script
$evidence = Join-Path $root 'build/ds013/evidence'

function Assert-ExitCode([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

function Invoke-Runner([string]$Method, [string]$Path) {
    $value = kubectl --context $context -n $namespace exec ds013-runner -- `
        atlas-kubernetes-client $Method $Path
    Assert-ExitCode "Falha ao invocar $Method $Path."
    return ($value -join "`n")
}

function Wait-Result([string]$ExecutionId, [int]$TimeoutSeconds = 120) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $status = Invoke-Runner 'GET' '/status'
        if ($status -match [regex]::Escape($ExecutionId)) { return }
        Start-Sleep -Milliseconds 200
    } while ((Get-Date) -lt $deadline)
    throw "Resultado não observado para $ExecutionId."
}

function Measure-Milliseconds([scriptblock]$Action) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    & $Action
    $watch.Stop()
    return [Math]::Round($watch.Elapsed.TotalMilliseconds, 3)
}

function Percentile([double[]]$Values, [double]$Percentile) {
    $ordered = @($Values | Sort-Object)
    $index = [Math]::Ceiling(($Percentile / 100) * $ordered.Count) - 1
    return $ordered[[Math]::Max(0, $index)]
}

$recoverySamples = @()
for ($index = 1; $index -le 10; $index++) {
    $executionId = 'benchmark-recovery-{0:d2}' -f $index
    $recoverySamples += Measure-Milliseconds {
        Invoke-Runner 'POST' "/seed?backend=postgresql&execution_id=$executionId&decision=approve" | Out-Null
        Wait-Result $executionId
    }
}

$podStartup = Measure-Milliseconds {
    $pod = kubectl --context $context -n $namespace get pods `
        -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    kubectl --context $context -n $namespace delete pod $pod --wait=true | Out-Null
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s | Out-Null
    Assert-ExitCode 'O replacement usado no benchmark não ficou pronto.'
}

$scaleOut = Measure-Milliseconds {
    kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=3 | Out-Null
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s | Out-Null
    Assert-ExitCode 'O scale out do benchmark falhou.'
}
$scaleIn = Measure-Milliseconds {
    kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=2 | Out-Null
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s | Out-Null
    Assert-ExitCode 'O scale in do benchmark falhou.'
}
$rolling = Measure-Milliseconds {
    kubectl --context $context -n $namespace rollout restart deployment/atlas-worker | Out-Null
    kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s | Out-Null
    Assert-ExitCode 'O rolling update do benchmark falhou.'
}

$leaseExecution = 'benchmark-lease-expiration'
$leaseRecovery = Measure-Milliseconds {
    Invoke-Runner 'POST' "/seed?backend=postgresql&execution_id=$leaseExecution&decision=pending" | Out-Null
    Invoke-Runner 'POST' "/arm-crash-after-effect?execution_id=$leaseExecution" | Out-Null
    Invoke-Runner 'POST' "/decide?execution_id=$leaseExecution&decision=approve" | Out-Null
    Wait-Result $leaseExecution
}

$payload = [ordered]@{
    measured_at = (Get-Date).ToUniversalTime().ToString('o')
    kubernetes_server = 'v1.31.2'
    container_runtime = 'containerd 1.7.24 / Docker Desktop 29.8.1'
    cluster_topology = 'kind; 1 control-plane node; Calico 3.31.7'
    python = '3.12.15'
    atlas = '1.0.1'
    postgresql = '16.10'
    redis = '7.4.5; AOF always; noeviction; standalone'
    worker_replicas = 2
    checkpoint_payload = 'HITL deterministic certification checkpoint'
    recovery_samples_ms = $recoverySamples
    recovery_median_ms = Percentile $recoverySamples 50
    recovery_p95_ms = Percentile $recoverySamples 95
    pod_startup_and_readiness_ms = $podStartup
    scale_out_ms = $scaleOut
    scale_in_ms = $scaleIn
    rolling_update_ms = $rolling
    lease_expiration_and_recovery_ms = $leaseRecovery
    failures = 0
}
$payload | ConvertTo-Json -Depth 4 | Out-File `
    (Join-Path $evidence 'performance-baseline.json') -Encoding utf8
Write-Output ($payload | ConvertTo-Json -Depth 4)
