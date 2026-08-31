$ErrorActionPreference = "Stop"

$health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/healthz" -TimeoutSec 30
if ($health.status -ne "ok") {
    throw "D&D Tools health check failed."
}

$models = Invoke-RestMethod -Uri "http://127.0.0.1:11435/api/tags" -TimeoutSec 30
if (-not ($models.models.name -contains "qwen2.5:3b")) {
    throw "The campaign model is not installed in Ollama."
}

$request = @{
    model = "campaign-local"
    messages = @(
        @{ role = "user"; content = "Reply with exactly READY" }
    )
    max_tokens = 10
} | ConvertTo-Json -Depth 5

$completion = Invoke-RestMethod `
    -Uri "http://127.0.0.1:4000/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer local-kind" } `
    -Body $request `
    -TimeoutSec 300

if (-not $completion.choices[0].message.content) {
    throw "LiteLLM did not return a model response."
}

kubectl --namespace dnd-tools get pods
Write-Host "Health, model installation, and LiteLLM inference checks passed."
