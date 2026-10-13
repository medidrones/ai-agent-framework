[CmdletBinding()]
param(
    [switch]$KeepNamespace
)

$ErrorActionPreference = 'Stop'
$context = 'kind-atlas-ds013'
$namespace = 'atlas-ds013'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$example = Join-Path $root 'examples/kubernetes-recovery'
$evidence = Join-Path $root 'build/ds014/evidence'
$kubectl = Join-Path $root 'build/ds013/kubectl-v1.31.2.exe'
$kindCandidate = Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Packages/Kubernetes.kind_Microsoft.Winget.Source_8wekyb3d8bbwe/kind.exe'
$kindCommand = Get-Command kind -ErrorAction SilentlyContinue
$kind = if ($null -ne $kindCommand) { $kindCommand.Source } elseif (Test-Path -LiteralPath $kindCandidate) { $kindCandidate } else { throw 'kind não foi encontrado.' }

function Assert-ExitCode([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

function Invoke-Runner([string]$Method, [string]$Path) {
    $value = & $kubectl --context $context -n $namespace exec ds013-runner -- `
        atlas-kubernetes-client $Method $Path
    Assert-ExitCode "Falha ao invocar $Method $Path."
    return ($value -join "`n") | ConvertFrom-Json
}

function Invoke-RunnerJson([string]$Path, [hashtable]$Body) {
    $serialized = $Body | ConvertTo-Json -Compress -Depth 8
    $value = $serialized | & $kubectl --context $context -n $namespace exec -i ds013-runner -- `
        atlas-kubernetes-client POST $Path --json-stdin
    Assert-ExitCode "Falha ao invocar POST $Path com JSON."
    return ($value -join "`n") | ConvertFrom-Json
}

function New-DecisionBody([object]$Seed, [string]$Decision, [string]$DecisionId) {
    return @{
        decision_id = $DecisionId
        approval_request_id = $Seed.approval_request_id
        execution_id = $Seed.execution_id
        tenant_id = $Seed.tenant_id
        tool_call_id = $Seed.tool_call_id
        tool_name = $Seed.tool_name
        decision = $Decision
        subject = 'ds014-human-owner'
        principal_tenant_id = 'tenant-ds014'
        permissions = @('atlas:hitl:decide')
        tool_names = @('record_certification_effect')
        resume_token = $Seed.resume_token
        reason = 'Decisão explícita da certificação DS-014.'
    }
}

if (-not (Test-Path -LiteralPath $kubectl)) {
    throw 'Execute scripts/prepare_ds013_cluster.ps1 antes da DS-014.'
}
if (Test-Path -LiteralPath $evidence) {
    $resolved = (Resolve-Path -LiteralPath $evidence).Path
    $expected = Join-Path $root 'build/ds014/evidence'
    if ($resolved -ne $expected) { throw 'Diretório de evidências inesperado.' }
    Get-ChildItem -LiteralPath $evidence -Force | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

try {
    $currentContext = & $kubectl config current-context
    if ($currentContext -ne $context) { throw "Contexto inesperado: $currentContext" }
    & docker build --file (Join-Path $example 'Dockerfile') --tag atlas-ds013:1.0.1 $root
    Assert-ExitCode 'Falha ao reconstruir a imagem DS-014.'
    & $kind load docker-image atlas-ds013:1.0.1 --name atlas-ds013
    Assert-ExitCode 'Falha ao carregar a imagem DS-014 no kind.'
    & $kubectl --context $context -n $namespace rollout restart deployment/atlas-worker
    & $kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=240s
    Assert-ExitCode 'O worker atualizado não ficou disponível.'
    & $kubectl --context $context -n $namespace delete pod ds013-runner --ignore-not-found --wait=true | Out-Null
    & $kubectl --context $context -n $namespace run ds013-runner `
        --image=atlas-ds013:1.0.1 --image-pull-policy=Never --restart=Never `
        --labels='atlas.medicode.dev/certification-runner=true' `
        --command -- sleep 7200
    & $kubectl --context $context -n $namespace wait pod/ds013-runner --for=condition=Ready --timeout=120s
    Assert-ExitCode 'O runner DS-014 não ficou pronto.'

    $postgresSeed = Invoke-Runner 'POST' '/durable-hitl/seed?backend=postgresql&execution_id=ds014-postgresql-pod-restart&tenant_id=tenant-ds014'
    $tokenToProtect = $postgresSeed.resume_token
    $pod = & $kubectl --context $context -n $namespace get pods -l app.kubernetes.io/name=atlas-worker -o jsonpath='{.items[0].metadata.name}'
    & $kubectl --context $context -n $namespace delete pod $pod --wait=true | Out-Null
    & $kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=180s
    $postgresResult = Invoke-RunnerJson '/durable-hitl/decide' (New-DecisionBody $postgresSeed 'approve' 'decision-postgresql-restart')
    if ($postgresResult.resume_outcome -ne 'completed') { throw 'A retomada PostgreSQL após restart falhou.' }
    $postgresAudit = Invoke-Runner 'GET' "/durable-hitl/audit?approval_request_id=$($postgresSeed.approval_request_id)"
    $postgresAudit | ConvertTo-Json -Depth 8 | Out-File (Join-Path $evidence 'postgresql-pod-restart.json') -Encoding utf8

    $redisSeed = Invoke-Runner 'POST' '/durable-hitl/seed?backend=redis&execution_id=ds014-redis-rolling-pending&tenant_id=tenant-ds014'
    & $kubectl --context $context -n $namespace rollout restart deployment/atlas-worker
    & $kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=240s
    $redisResult = Invoke-RunnerJson '/durable-hitl/decide' (New-DecisionBody $redisSeed 'reject' 'decision-redis-rolling')
    if ($redisResult.resume_outcome -ne 'rejected') { throw 'A rejeição Redis após rolling update falhou.' }
    $redisAudit = Invoke-Runner 'GET' "/durable-hitl/audit?approval_request_id=$($redisSeed.approval_request_id)"
    $redisAudit | ConvertTo-Json -Depth 8 | Out-File (Join-Path $evidence 'redis-rolling-rejection.json') -Encoding utf8

    & $kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=10
    & $kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=300s
    Assert-ExitCode 'Os dez workers de recovery não ficaram disponíveis.'
    $loadRaw = & $kubectl --context $context -n $namespace exec ds013-runner -- `
        atlas-kubernetes-hitl-certify --count 100 --pending 50 --concurrent 100
    Assert-ExitCode 'A carga operacional DS-014 falhou.'
    $loadRaw -join "`n" | Out-File (Join-Path $evidence 'performance.json') -Encoding utf8
    $load = ($loadRaw -join "`n") | ConvertFrom-Json
    if ($load.sequential_approvals.outcomes.completed -ne 100) { throw 'As 100 aprovações sequenciais não concluíram.' }
    if ($load.sequential_rejections.outcomes.rejected -ne 100) { throw 'As 100 rejeições sequenciais não concluíram.' }
    if ($load.concurrent_resume.outcomes.completed -ne 1) { throw 'A corrida de resume não teve um vencedor.' }
    if ($load.concurrent_resume.outcomes.already_consumed -ne 99) { throw 'A corrida de resume não rejeitou 99 replays.' }
    if ($load.pending_suspensions -ne 50) { throw 'As 50 suspensões long-lived não foram criadas.' }

    $workerLogs = & $kubectl --context $context -n $namespace logs -l app.kubernetes.io/name=atlas-worker --all-containers=true --prefix=true
    $workerLogs -join "`n" | Out-File (Join-Path $evidence 'worker-logs.txt') -Encoding utf8
    if (($workerLogs -join "`n").Contains($tokenToProtect)) { throw 'O token apareceu nos logs do worker.' }
    if (($postgresAudit | ConvertTo-Json -Depth 8).Contains($tokenToProtect)) { throw 'O token apareceu na auditoria durável.' }
    & $kubectl --context $context -n $namespace get pods,deployments,services -o wide | Out-File (Join-Path $evidence 'cluster-state.txt') -Encoding utf8
    & $kubectl --context $context version -o yaml | Out-File (Join-Path $evidence 'kubernetes-version.yaml') -Encoding utf8
    & $kubectl --context $context -n $namespace scale deployment/atlas-worker --replicas=2
    & $kubectl --context $context -n $namespace rollout status deployment/atlas-worker --timeout=240s
}
finally {
    if (-not $KeepNamespace) {
        if ($namespace -ne 'atlas-ds013') { throw 'Namespace de limpeza inesperado.' }
        & $kubectl --context $context delete namespace $namespace --wait=true --timeout=180s
    }
}
