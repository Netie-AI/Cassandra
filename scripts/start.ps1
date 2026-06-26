# scripts/start.ps1 — THE launch command
# Usage: .\scripts\start.ps1
# Usage: .\scripts\start.ps1 -Run   <- also triggers one pipeline run immediately

param([switch]$Run)
Set-Location (Split-Path $PSScriptRoot)

Get-Content .env | Where-Object { $_ -match '^\s*[^#]' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    if ($k) { [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), 'Process') }
}

if ($Run) {
    Write-Host "[Cassandra] Running pipeline..." -ForegroundColor Cyan
    python -m src.orchestrator --run
}

Write-Host "[Cassandra] Starting API on http://localhost:8080" -ForegroundColor Green
python -m uvicorn api.main:app --port 8080 --reload
