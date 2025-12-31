$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envPath = Join-Path $repoRoot '.env'
$examplePath = Join-Path $repoRoot '.env.example'

function Read-EnvFile([string]$path) {
  $map = @{}
  if (-not (Test-Path $path)) { return $map }
  Get-Content $path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }
    if ($line.StartsWith('#')) { return }
    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }
    $k = $line.Substring(0, $idx).Trim()
    $v = $line.Substring($idx + 1).Trim()
    $map[$k] = $v
  }
  return $map
}

function Write-EnvFile([string]$path, [hashtable]$map) {
  function GetVal([string]$key, [string]$default = '') {
    if ($map.ContainsKey($key) -and $null -ne $map[$key]) {
      return [string]$map[$key]
    }
    return $default
  }

  $lines = @()
  $lines += 'OPENAI_API_KEY=' + (GetVal 'OPENAI_API_KEY' '')
  $lines += 'ANTHROPIC_API_KEY=' + (GetVal 'ANTHROPIC_API_KEY' '')
  $lines += ''
  $lines += '# If using LiteLLM Proxy (recommended for unified OpenAI/Claude/local models), set:'
  $lines += '# Example: http://localhost:4000'
  $lines += 'LITELLM_BASE_URL=' + (GetVal 'LITELLM_BASE_URL' '')
  $lines += '# Optional (if your proxy uses a key):'
  $lines += 'LITELLM_API_KEY=' + (GetVal 'LITELLM_API_KEY' '')
  $lines += ''
  $lines += '# Default model name/alias used by the generators'
  $lines += '# Example: gpt-5.2, claude-3-5-sonnet, or a LiteLLM model alias'
  $lines += 'DND_DEFAULT_MODEL=' + (GetVal 'DND_DEFAULT_MODEL' 'gpt-5.2')
  $lines += ''
  $lines += '# Optional: secure LiteLLM proxy (docker-compose)'
  $lines += 'LITELLM_MASTER_KEY=' + (GetVal 'LITELLM_MASTER_KEY' '')

  Set-Content -Path $path -Value $lines -Encoding UTF8
}

# Bootstrap .env if missing
if (-not (Test-Path $envPath)) {
  if (Test-Path $examplePath) {
    Copy-Item $examplePath $envPath
  } else {
    New-Item -ItemType File -Path $envPath | Out-Null
  }
}

$envMap = Read-EnvFile $envPath

# Helper to decide whether to prompt
function NeedsValue([string]$val) {
  if (-not $val) { return $true }
  $v = $val.Trim()
  if (-not $v) { return $true }
  if ($v -like '*your_*_api_key_here*') { return $true }
  return $false
}

Write-Host "Ensuring local .env exists at $envPath"
Write-Host "(Keys are stored locally; .env is gitignored.)"

$nonInteractive = $false
if ($env:CI -eq 'true' -or $env:CI -eq '1' -or $env:TASK_NONINTERACTIVE -eq '1') {
  $nonInteractive = $true
  Write-Host "Non-interactive mode: skipping prompts (CI/TASK_NONINTERACTIVE)."
}

# Prompt for keys only if missing. Allow skipping.
if (-not $nonInteractive) {
  if (NeedsValue $envMap['OPENAI_API_KEY']) {
    $in = Read-Host 'OPENAI_API_KEY (press Enter to skip)'
    if ($in) { $envMap['OPENAI_API_KEY'] = $in }
  }

  if (NeedsValue $envMap['ANTHROPIC_API_KEY']) {
    $in = Read-Host 'ANTHROPIC_API_KEY (press Enter to skip)'
    if ($in) { $envMap['ANTHROPIC_API_KEY'] = $in }
  }

  if (NeedsValue $envMap['LITELLM_BASE_URL']) {
    $in = Read-Host 'LITELLM_BASE_URL (press Enter to skip; e.g. http://localhost:4000)'
    if ($in) { $envMap['LITELLM_BASE_URL'] = $in }
  }

  if (NeedsValue $envMap['DND_DEFAULT_MODEL']) {
    $in = Read-Host 'DND_DEFAULT_MODEL (press Enter for gpt-5.2)'
    if ($in) { $envMap['DND_DEFAULT_MODEL'] = $in } else { $envMap['DND_DEFAULT_MODEL'] = 'gpt-5.2' }
  }

  # If using LiteLLM master key, keep LITELLM_API_KEY in sync unless user overrides.
  if (NeedsValue $envMap['LITELLM_MASTER_KEY']) {
    $in = Read-Host 'LITELLM_MASTER_KEY (optional; press Enter to skip)'
    if ($in) { $envMap['LITELLM_MASTER_KEY'] = $in }
  }
}

if ((-not (NeedsValue $envMap['LITELLM_MASTER_KEY'])) -and (NeedsValue $envMap['LITELLM_API_KEY'])) {
  $envMap['LITELLM_API_KEY'] = $envMap['LITELLM_MASTER_KEY']
}

Write-EnvFile $envPath $envMap
Write-Host "Wrote $envPath"