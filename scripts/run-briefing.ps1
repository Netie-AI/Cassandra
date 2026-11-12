# Cassandra AI Briefing runner — call from Task Scheduler (see register-briefing-tasks.ps1).
# -Edition auto picks morning / evening / weekly from config/briefing.yaml (Singapore time)
# and exits quietly when nothing is due.
param([string]$Edition = "auto", [switch]$NoSend)
Set-Location (Join-Path $PSScriptRoot "..")
$venv = Join-Path $PSScriptRoot "..\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv } else { Write-Host "[WARN] No venv found — using system Python" }
New-Item -ItemType Directory -Force -Path "reports\briefings" | Out-Null
$log = "reports\briefings\run.log"
$cmd = @("-m", "src.briefing", "--edition", $Edition)
if (-not $NoSend) { $cmd += "--send" }
python @cmd 2>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    Write-Error "[BRIEFING] exited $LASTEXITCODE — see $log"
    exit $LASTEXITCODE
}
