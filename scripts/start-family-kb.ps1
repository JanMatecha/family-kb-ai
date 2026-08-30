[CmdletBinding()]
param(
    [int]$DockerTimeoutSeconds = 120,
    [int]$QdrantTimeoutSeconds = 60,
    [switch]$RunDiagnostics
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Test-DockerEngine {
    try {
        & docker info *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-Qdrant {
    try {
        Invoke-RestMethod `
            -Uri "http://localhost:6333/collections" `
            -Method Get `
            -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Wait-ForCondition {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Condition,
        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (& $Condition) {
            return $true
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    return $false
}

Write-Host "=== Family KB startup ==="
Write-Host "Repository: $repoRoot"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI was not found. Install Docker Desktop first."
}

if (-not (Test-DockerEngine)) {
    $dockerDesktop = Join-Path $Env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktop)) {
        throw "Docker Desktop executable was not found at: $dockerDesktop"
    }

    Write-Host "Docker engine is not running. Starting Docker Desktop..."
    Start-Process $dockerDesktop | Out-Null

    $dockerReady = Wait-ForCondition `
        -Condition { Test-DockerEngine } `
        -TimeoutSeconds $DockerTimeoutSeconds

    if (-not $dockerReady) {
        throw "Docker engine did not become ready within $DockerTimeoutSeconds seconds."
    }
}

Write-Host "Docker engine: OK"

Write-Host "Starting Qdrant with Docker Compose..."
& docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw "docker compose up -d failed with exit code $LASTEXITCODE."
}

$qdrantReady = Wait-ForCondition `
    -Condition { Test-Qdrant } `
    -TimeoutSeconds $QdrantTimeoutSeconds

if (-not $qdrantReady) {
    throw "Qdrant did not become ready within $QdrantTimeoutSeconds seconds."
}

Write-Host "Qdrant: OK"
Write-Host "Qdrant dashboard: http://localhost:6333/dashboard"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Warning "uv was not found on PATH."
    Write-Warning "Install uv, then run: uv sync"
}
else {
    & uv run --no-sync family-kb --help *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "uv: OK"
        Write-Host "Family KB CLI: OK"
    }
    else {
        Write-Warning "Family KB uv environment is missing or out of sync."
        Write-Warning "Run: uv sync"
    }
}

Write-Host ""
Write-Host "Family KB environment is ready."

if ($RunDiagnostics) {
    Write-Host ""
    Write-Host "Running diagnostics..."
    & (Join-Path $PSScriptRoot "diagnose-family-kb.ps1")
}
