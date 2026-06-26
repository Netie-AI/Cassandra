param([string]$Dest = "D:\Cassandra-backup")

$Src = "C:\Users\OoiJianHong\Cassandra"

if (-not (Test-Path (Split-Path $Dest -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $Dest -Parent) -Force | Out-Null
}
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

Write-Host "Copying repo to $Dest ..."
robocopy $Src $Dest /E /XD .venv __pycache__ node_modules /XF "*.pyc" | Out-Null

if (Test-Path "$Src\.env") {
    Copy-Item "$Src\.env" "$Dest\.env" -Force
    Write-Host "Copied .env"
}

if (Test-Path "$Src\reports") {
    robocopy "$Src\reports" "$Dest\reports" /E | Out-Null
}
if (Test-Path "$Src\knowledge") {
    robocopy "$Src\knowledge" "$Dest\knowledge" /E | Out-Null
}

@"
RESTORE ON NEW LAPTOP
=====================
1. Copy this folder to new machine
2. cd Cassandra-backup
3. python -m venv .venv
4. .\.venv\Scripts\Activate.ps1
5. pip install -r requirements.txt
6. Copy .env to project root
7. .\scripts\start.ps1
8. Import scripts\register-task-*.xml into Task Scheduler
"@ | Set-Content "$Dest\RESTORE.md" -Encoding UTF8

Write-Host "Done. Check $Dest"
