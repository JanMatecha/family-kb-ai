[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = "Continue"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $repoRoot "system_check.txt"
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repoRoot $OutputPath
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

function Convert-ToCleanText {
    param(
        [object[]]$Value
    )

    if ($null -eq $Value) {
        return ""
    }

    $text = ($Value | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    return ($text -replace "`0", "").TrimEnd()
}

function Add-Log {
    param(
        [string]$Text = ""
    )

    $clean = $Text -replace "`0", ""
    Add-Content -Path $OutputPath -Value $clean -Encoding UTF8
}

function Add-NativeSection {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Add-Log ""
    Add-Log "=== $Title ==="

    try {
        $raw = & $Command 2>&1
        $text = Convert-ToCleanText $raw
        if ($text) {
            Add-Log $text
        }
        else {
            Add-Log "(no output)"
        }
    }
    catch {
        Add-Log "ERROR: $($_.Exception.Message)"
    }
}

function Invoke-PythonSnippet {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Python,
        [Parameter(Mandatory = $true)]
        [string]$Code
    )

    $tempFile = Join-Path `
        ([System.IO.Path]::GetTempPath()) `
        ("family-kb-diagnostic-{0}.py" -f [guid]::NewGuid().ToString("N"))

    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tempFile, $Code, $utf8NoBom)
        $raw = & $Python $tempFile 2>&1
        return Convert-ToCleanText $raw
    }
    finally {
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    }
}

Set-Content `
    -Path $OutputPath `
    -Value "=== SYSTEM CHECK $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" `
    -Encoding UTF8

Add-NativeSection -Title "WSL STATUS" -Command {
    & wsl.exe --status
}

Add-NativeSection -Title "WSL DISTRIBUTIONS" -Command {
    & wsl.exe -l -v
}

Add-NativeSection -Title "DOCKER VERSION" -Command {
    & docker version
}

Add-NativeSection -Title "GIT STATUS" -Command {
    & git status --short --branch
}

Add-NativeSection -Title "GIT HEAD" -Command {
    & git log -1 --oneline
}

Add-NativeSection -Title "DOCKER COMPOSE" -Command {
    & docker compose ps
}

Add-Log ""
Add-Log "=== QDRANT COLLECTIONS ==="
try {
    $qdrant = Invoke-RestMethod `
        -Uri "http://localhost:6333/collections" `
        -Method Get `
        -TimeoutSec 5
    Add-Log ($qdrant | ConvertTo-Json -Depth 10)
}
catch {
    Add-Log "Qdrant is not available: $($_.Exception.Message)"
}

Add-NativeSection -Title "UV VERSION" -Command {
    & uv --version
}

Add-Log ""
Add-Log "=== FAMILY KB CLI ==="
if (Get-Command uv -ErrorAction SilentlyContinue) {
    try {
        $raw = & uv run --no-sync family-kb --help 2>&1
        Add-Log (Convert-ToCleanText $raw)
    }
    catch {
        Add-Log "ERROR: $($_.Exception.Message)"
    }
}
else {
    Add-Log "uv is not available on PATH."
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
Add-Log ""
Add-Log "=== UV-MANAGED PYTHON ENVIRONMENT ==="
if (Test-Path $python) {
    try {
        $raw = & $python --version 2>&1
        Add-Log (Convert-ToCleanText $raw)
    }
    catch {
        Add-Log "ERROR: $($_.Exception.Message)"
    }

    try {
        $pythonInfo = @'
import family_kb_ai
import torch
print("family-kb:", family_kb_ai.__version__)
print("torch:", torch.__version__)
print("cuda:", torch.cuda.is_available())
'@
        Add-Log (Invoke-PythonSnippet -Python $python -Code $pythonInfo)
    }
    catch {
        Add-Log "ERROR: $($_.Exception.Message)"
    }
}
else {
    Add-Log "Missing uv-managed environment: $python"
    Add-Log "Run: uv sync"
}

Add-Log ""
Add-Log "=== CONFIG / KB PATH ==="
if ((Test-Path $python) -and (Test-Path (Join-Path $repoRoot "config.yaml"))) {
    try {
        $configInfo = @'
from family_kb_ai.config import load_settings
s = load_settings("config.yaml")
print("kb_path:", s.kb_path)
print("kb_path_exists:", s.kb_path.is_dir())
print("qdrant_url:", s.qdrant_url)
print("qdrant_collection:", s.qdrant_collection)
print("embedding_model:", s.embedding_model)
'@
        Add-Log (Invoke-PythonSnippet -Python $python -Code $configInfo)
    }
    catch {
        Add-Log "ERROR: $($_.Exception.Message)"
    }
}
else {
    Add-Log "config.yaml or uv-managed Python environment is missing."
}

Add-Log ""
Add-Log "=== END ==="

Write-Host "Diagnostics complete."
Write-Host "UTF-8 report: $OutputPath"
