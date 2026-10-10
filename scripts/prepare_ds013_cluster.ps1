[CmdletBinding()]
param(
    [switch]$Recreate
)

$ErrorActionPreference = 'Stop'
$clusterName = 'atlas-ds013'
$contextName = 'kind-atlas-ds013'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$kindConfig = Join-Path $root 'examples/kubernetes-recovery/kind-config.yaml'
$calicoDockerDesktopPatch = Join-Path $root 'examples/kubernetes-recovery/calico-docker-desktop-patch.json'
$calicoPath = Join-Path $root 'build/ds013/calico-v3.31.7.yaml'
$calicoUri = 'https://raw.githubusercontent.com/projectcalico/calico/v3.31.7/manifests/calico.yaml'
$calicoSha256 = 'D6D8A489A4ED8E5B8EFD8B339047B496CA657B55EE2E3618E791507B0A853E8D'
$nodeImage = 'kindest/node:v1.31.2@sha256:18fbefc20a7113353c7b75b5c869d7145a6abd6269154825872dc59c1329912e'
$kubectlPath = Join-Path $root 'build/ds013/kubectl-v1.31.2.exe'
$kubectlChecksumPath = "$kubectlPath.sha256"
$kubectlUri = 'https://dl.k8s.io/release/v1.31.2/bin/windows/amd64/kubectl.exe'
$kubectlChecksumUri = "$kubectlUri.sha256"

function Resolve-Kind {
    $command = Get-Command kind -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $candidate = Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Packages/Kubernetes.kind_Microsoft.Winget.Source_8wekyb3d8bbwe/kind.exe'
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    throw 'kind não foi encontrado. Instale Kubernetes.kind pelo WinGet.'
}

function Resolve-Kubectl {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $kubectlPath) | Out-Null
    if (-not (Test-Path -LiteralPath $kubectlPath)) {
        Invoke-WebRequest -UseBasicParsing -Uri $kubectlUri -OutFile $kubectlPath
    }
    if (-not (Test-Path -LiteralPath $kubectlChecksumPath)) {
        Invoke-WebRequest -UseBasicParsing -Uri $kubectlChecksumUri -OutFile $kubectlChecksumPath
    }
    $expected = (Get-Content -LiteralPath $kubectlChecksumPath).Trim().ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $kubectlPath).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw 'Checksum do kubectl v1.31.2 inválido.' }
    return $kubectlPath
}

$kind = Resolve-Kind
$script:kubectlExecutable = Resolve-Kubectl
Set-Alias -Name kubectl -Value $script:kubectlExecutable -Scope Script
$clusters = @(& $kind get clusters)
if ($Recreate -and $clusters -contains $clusterName) {
    & $kind delete cluster --name $clusterName
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao remover o cluster DS-013.' }
    $clusters = @(& $kind get clusters)
}
if ($clusters -notcontains $clusterName) {
    & $kind create cluster --name $clusterName --image $nodeImage --config $kindConfig
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o cluster DS-013.' }
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $calicoPath) | Out-Null
if (-not (Test-Path -LiteralPath $calicoPath)) {
    Invoke-WebRequest -Uri $calicoUri -OutFile $calicoPath
}
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $calicoPath).Hash
if ($actualHash -ne $calicoSha256) {
    throw "Checksum inesperado do manifest Calico: $actualHash"
}

kubectl --context $contextName apply -f $calicoPath
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar o Calico.' }
# Docker Desktop sobre WSL2 não expõe securityfs e mantém /sys somente leitura.
# O patch estratégico usa as merge keys da API e permanece idempotente mesmo se a
# ordem dos volumes mudar no manifesto upstream.
$patchApplied = $false
foreach ($attempt in 1..5) {
    kubectl --context $contextName -n kube-system patch daemonset calico-node `
        --type=strategic --patch-file $calicoDockerDesktopPatch
    if ($LASTEXITCODE -eq 0) {
        $patchApplied = $true
        break
    }
    Start-Sleep -Seconds (2 * $attempt)
}
if (-not $patchApplied) { throw 'Falha ao compatibilizar o Calico com Docker Desktop.' }
kubectl --context $contextName rollout status daemonset/calico-node -n kube-system --timeout=240s
kubectl --context $contextName rollout status deployment/calico-kube-controllers -n kube-system --timeout=240s
kubectl --context $contextName wait node --all --for=condition=Ready --timeout=240s
if ($LASTEXITCODE -ne 0) { throw 'O cluster não atingiu o estado Ready.' }

kubectl --context $contextName version -o yaml
kubectl --context $contextName get nodes -o wide
