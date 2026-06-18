$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

$projects = @(
    "day01_schema_fastapi",
    "day02_llm_budget"
)

foreach ($project in $projects) {
    $projectPath = Join-Path $root $project
    Write-Host "=== Testing $project ==="
    Push-Location $projectPath
    try {
        & $python -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed for $project"
        }
    }
    finally {
        Pop-Location
    }
}

