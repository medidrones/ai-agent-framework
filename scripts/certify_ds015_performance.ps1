param(
    [Parameter(Mandatory = $true)]
    [string]$PostgreSqlDsn,
    [Parameter(Mandatory = $true)]
    [string]$RedisUrl,
    [Parameter(Mandatory = $true)]
    [switch]$ConfirmTestEnvironment,
    [int]$Samples = 30,
    [int]$SoakSeconds = 3600,
    [int]$SoakConcurrency = 50
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $repository "examples/kubernetes-recovery/src/atlas_kubernetes_recovery/performance_certifier.py"
$results = Join-Path $repository "docs/roadmap-2/m01-durable-state/ds-015/results"

if (-not $ConfirmTestEnvironment) {
    throw "Confirme explicitamente o ambiente isolado de testes."
}
if ($Samples -lt 2) {
    throw "Use ao menos duas amostras."
}
if ($SoakSeconds -lt 3600) {
    throw "A certificação exige soak de pelo menos 3.600 segundos."
}

New-Item -ItemType Directory -Force -Path $results | Out-Null

$common = @(
    "run", "python", $runner,
    "--samples", $Samples,
    "--concurrency", 1, 10, 50, 100, 250, 500,
    "--payloads", 1024, 16384, 262144, 1048576,
    "--soak-seconds", $SoakSeconds,
    "--soak-concurrency", $SoakConcurrency,
    "--confirm-test-environment"
)

& uv @common --backend postgresql --dsn $PostgreSqlDsn `
    --output (Join-Path $results "postgresql.json")
if ($LASTEXITCODE -ne 0) {
    throw "A certificação PostgreSQL falhou."
}

& uv @common --backend redis --url $RedisUrl `
    --output (Join-Path $results "redis.json")
if ($LASTEXITCODE -ne 0) {
    throw "A certificação Redis falhou."
}

Write-Host "Resultados DS-015 gravados em $results"
