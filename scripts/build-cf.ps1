# Patch web/static/_redirects with live Worker URL (not committed to git).
param([string]$WorkerUrl = $env:CF_WORKER_URL)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Redirects = Join-Path $Root "web\static\_redirects"
if (-not $WorkerUrl) {
    Write-Error "CF_WORKER_URL not set — export in .env or pass -WorkerUrl"
    exit 1
}
if (-not (Test-Path $Redirects)) {
    Write-Error "_redirects not found at $Redirects"
    exit 1
}
(Get-Content $Redirects -Raw) -replace 'YOUR_WORKER_URL', $WorkerUrl | Set-Content $Redirects -NoNewline
Write-Host "[OK] _redirects patched with $WorkerUrl"
