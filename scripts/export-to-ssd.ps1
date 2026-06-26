param(
    [string]$Dest = "D:\Cassandra-backup",
    [string]$Src = ""
)

if (-not $Src) {
    $Src = Split-Path $PSScriptRoot -Parent
}

if (-not (Test-Path $Src)) {
    Write-Error "Source not found: $Src"
    exit 1
}

$parent = Split-Path $Dest -Parent
if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

Write-Host "Copying $Src -> $Dest ..."
robocopy $Src $Dest /E /XD .venv __pycache__ node_modules .pytest_cache /XF "*.pyc" "hi.pdf"
$rc = $LASTEXITCODE
if ($rc -ge 8) {
    Write-Error "robocopy failed with exit code $rc"
    exit $rc
}

if (Test-Path "$Src\.env") {
    Copy-Item "$Src\.env" "$Dest\.env" -Force
    Write-Host "Copied .env"
} else {
    Write-Warning ".env not found in source; copy manually before restore"
}

# Drop stale secrets that may linger from older backups
@("Cpanel.md", "hi.pdf") | ForEach-Object {
    $stale = Join-Path $Dest $_
    if (Test-Path $stale) { Remove-Item $stale -Force }
}

if (Test-Path "$Src\reports") {
    robocopy "$Src\reports" "$Dest\reports" /E
}
if (Test-Path "$Src\knowledge") {
    robocopy "$Src\knowledge" "$Dest\knowledge" /E
}

@"
RESTORE ON NEW LAPTOP
=====================
1. Copy this folder to the new machine (e.g. C:\Users\<you>\Cassandra)
2. cd into the project root
3. powershell -ExecutionPolicy Bypass -File .\scripts\setup-new-machine.ps1
4. Verify .env is present in project root (included in this backup)
5. .\scripts\start.ps1
6. Import scripts\register-task-*.xml into Task Scheduler
"@ | Set-Content "$Dest\RESTORE.md" -Encoding UTF8

Write-Host "Done. Backup at $Dest (robocopy exit $rc)"
