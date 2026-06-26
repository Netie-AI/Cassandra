Set-Location (Split-Path $PSScriptRoot -Parent)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet
Write-Host "Ready. Run: .\scripts\start.ps1"
