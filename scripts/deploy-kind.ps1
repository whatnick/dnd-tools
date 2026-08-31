param(
    [switch]$Recreate
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$kind = Get-Command kind -ErrorAction Stop

& $env:ComSpec /c "docker info >nul 2>nul"
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running."
}

$clusterExists = (& $kind.Source get clusters) -contains "dnd-tools"
if ($Recreate -and $clusterExists) {
    & $kind.Source delete cluster --name dnd-tools
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to delete the existing kind cluster."
    }
    $clusterExists = $false
}

if (-not $clusterExists) {
    & $kind.Source create cluster --config "$root\k8s\kind-config.yaml"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the kind cluster."
    }
}

docker build --tag dnd-tools:local $root
if ($LASTEXITCODE -ne 0) {
    throw "Failed to build dnd-tools image."
}

& $kind.Source load docker-image dnd-tools:local --name dnd-tools
if ($LASTEXITCODE -ne 0) {
    throw "Failed to load the dnd-tools image into kind."
}

kubectl apply --filename "$root\k8s\dnd-tools.yaml"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply the core Kubernetes manifests."
}

kubectl --namespace dnd-tools rollout status deployment/ollama --timeout=10m
if ($LASTEXITCODE -ne 0) {
    throw "Ollama did not become ready."
}

kubectl --namespace dnd-tools delete job ollama-pull-campaign-model --ignore-not-found
kubectl apply --filename "$root\k8s\ollama-model-job.yaml"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the model pull job."
}

kubectl --namespace dnd-tools wait --for=condition=complete job/ollama-pull-campaign-model --timeout=30m
if ($LASTEXITCODE -ne 0) {
    kubectl --namespace dnd-tools logs job/ollama-pull-campaign-model
    throw "The model pull job did not complete."
}

kubectl --namespace dnd-tools rollout restart deployment/litellm
kubectl --namespace dnd-tools rollout status deployment/litellm --timeout=10m
if ($LASTEXITCODE -ne 0) {
    throw "LiteLLM did not become ready."
}

kubectl --namespace dnd-tools rollout restart deployment/dnd-tools
kubectl --namespace dnd-tools rollout status deployment/dnd-tools --timeout=5m
if ($LASTEXITCODE -ne 0) {
    throw "D&D Tools did not become ready."
}

Write-Host "D&D Tools is available at http://127.0.0.1:8000/campaigns"
