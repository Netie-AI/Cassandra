# Register Cassandra daily pipeline slots (UTC) in Windows Task Scheduler.
# Requires elevated PowerShell for schtasks /Create.
$ErrorActionPreference = "Continue"
$Root = "C:\Users\OoiJianHong\Cassandra"
$Script = Join-Path $Root "scripts\run-daily.ps1"
$Action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Script`""
$Slots = @(
    @{ Name = "Cassandra-Daily-0400UTC"; Time = "04:00" },
    @{ Name = "Cassandra-Daily-1300UTC"; Time = "13:00" },
    @{ Name = "Cassandra-Daily-1600UTC"; Time = "16:00" }
)

Write-Host "Registering $($Slots.Count) Cassandra tasks (UTC times; set Task Scheduler timezone to UTC)."
$ok = 0
foreach ($slot in $Slots) {
    schtasks /Delete /TN $slot.Name /F *>$null
    schtasks /Create /TN $slot.Name /TR $Action /SC DAILY /ST $slot.Time /RU $env:USERNAME /RL HIGHEST /F /IT *>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK  $($slot.Name) at $($slot.Time) UTC"
        $ok++
    } else {
        Write-Warning "  FAIL $($slot.Name) - run PowerShell as Administrator"
    }
}
Write-Host "Registered $ok / $($Slots.Count) tasks."
if ($ok -lt $Slots.Count) {
    Write-Host "Add Conditions in Task Scheduler: network available, AC power only, restart once after 5 min on failure."
    exit 1
}
exit 0
