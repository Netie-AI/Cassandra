# Cassandra daily runner — call from Task Scheduler
# API + ops desk: .\scripts\start.ps1
# Set OPS_PRERUN_MINUTES in .env or override here
param([string]$Run = "now")
Set-Location (Join-Path $PSScriptRoot "..")
$venv = Join-Path $PSScriptRoot "..\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    . $venv
} else {
    Write-Host "[WARN] No venv found — using system Python"
}
python -m src.orchestrator --run
if ($LASTEXITCODE -ne 0) {
    Write-Error "[CASSANDRA] Orchestrator exited $LASTEXITCODE"
    exit $LASTEXITCODE
}
