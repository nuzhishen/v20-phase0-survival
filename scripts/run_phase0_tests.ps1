$ErrorActionPreference = "Stop"

# Run each daily project in its own working directory.
# This avoids cross-day imports between separate top-level app packages.
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

# Prefer the repository virtualenv; fall back to system Python when needed.
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

# Phase 0 is integrated through Day 6. Each day still runs in its own
# process so top-level `app` packages do not collide.
$projects = @(
    "day01_schema_fastapi",
    "day02_llm_budget",
    "day03_react_loop",
    "day04_rag_pipeline",
    "day05_hybrid_rerank",
    "day06_pass_test"
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
