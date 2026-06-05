$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$collector = Join-Path $root 'scripts/collect_kiwoom_foreign_rank.ps1'
$csvOutput = Join-Path $root 'picks/cache/foreign_flow_history.kiwoom.test.csv'
$snapshotOutput = Join-Path $root 'picks/cache/foreign_rank_snapshot.kiwoom.test.json'
$streakOutput = Join-Path $root 'picks/cache/foreign_streak_candidates.kiwoom.test.json'

Remove-Item -Path $csvOutput -ErrorAction SilentlyContinue
Remove-Item -Path $snapshotOutput -ErrorAction SilentlyContinue
Remove-Item -Path $streakOutput -ErrorAction SilentlyContinue

if (-not (Test-Path $collector)) {
  throw "Missing Kiwoom foreign rank collector: $collector"
}

$run = & $collector -OfflineSample -OutputCsvPath $csvOutput -SnapshotPath $snapshotOutput -Days 3 -Top 5 2>&1
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($exitCode -ne 0) {
  throw "Kiwoom foreign rank collector offline sample failed with exit code $exitCode`n$($run -join "`n")"
}
if (-not (Test-Path $csvOutput)) {
  throw 'Kiwoom collector did not create foreign flow CSV'
}
if (-not (Test-Path $snapshotOutput)) {
  throw 'Kiwoom collector did not create rank snapshot'
}

$csv = Import-Csv -Path $csvOutput -Encoding UTF8
if (@($csv).Count -lt 6) {
  throw 'Kiwoom collector should write multiple ticker/date rows'
}
foreach ($required in @('date', 'ticker', 'name', 'foreign_net_buy', 'institution_net_buy', 'close', 'volume')) {
  if (-not ($csv[0].PSObject.Properties.Name -contains $required)) {
    throw "Kiwoom collector CSV missing column: $required"
  }
}

$snapshot = Get-Content -Path $snapshotOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($snapshot.provider -ne 'kiwoom') {
  throw 'Kiwoom snapshot should identify provider=kiwoom'
}
if ($snapshot.mode -ne 'offline_sample') {
  throw 'Kiwoom offline sample snapshot should use offline_sample mode'
}
if (@($snapshot.items).Count -lt 2) {
  throw 'Kiwoom snapshot should include ranked items'
}

$streakScanner = Join-Path $root 'scripts/find_foreign_streaks.ps1'
$streakRun = & $streakScanner -InputCsvPath $csvOutput -OutputPath $streakOutput -MinConsecutiveDays 3 -Top 5 2>&1
$streakExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($streakExitCode -ne 0) {
  throw "Foreign streak scanner failed on Kiwoom CSV with exit code $streakExitCode`n$($streakRun -join "`n")"
}

$streak = Get-Content -Path $streakOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($streak.candidates).Count -lt 1) {
  throw 'Kiwoom sample should produce at least one 3-day foreign streak candidate'
}
