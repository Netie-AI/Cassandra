# Register the AI Briefing slots in Windows Task Scheduler.
# Times are LOCAL machine time. Malaysia and Singapore share UTC+8, so no conversion is needed
# on a machine set to either. Keep these in step with config/briefing.yaml (the Python side
# re-checks the slot, so a task firing on the wrong day sends nothing).
# Run from an elevated PowerShell.
$ErrorActionPreference = "Continue"
$Script = Join-Path $PSScriptRoot "run-briefing.ps1"
$Action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Script`""
$Slots = @(
    @{ Name = "Cassandra-Briefing-Morning"; Time = "07:30"; Days = "TUE,WED,THU,FRI,SAT" },
    @{ Name = "Cassandra-Briefing-Evening"; Time = "20:30"; Days = "MON,TUE,WED,THU,FRI" },
    @{ Name = "Cassandra-Briefing-Weekly";  Time = "09:00"; Days = "SUN" }
)
$ok = 0
foreach ($slot in $Slots) {
    schtasks /Delete /TN $slot.Name /F *>$null
    schtasks /Create /TN $slot.Name /TR $Action /SC WEEKLY /D $slot.Days /ST $slot.Time /RU $env:USERNAME /RL HIGHEST /F /IT *>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK   $($slot.Name) $($slot.Days) $($slot.Time)"; $ok++ }
    else { Write-Warning "  FAIL $($slot.Name) - run PowerShell as Administrator" }
}
Write-Host "Registered $ok / $($Slots.Count) briefing tasks."
if ($ok -lt $Slots.Count) { exit 1 }
