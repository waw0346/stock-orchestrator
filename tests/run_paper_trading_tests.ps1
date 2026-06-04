$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$simulator = Join-Path $root 'scripts/paper_trade_simulator.ps1'
$rules = Join-Path $root 'picks/paper_trading_rules.json'
$prices = Join-Path $root 'picks/paper_price_snapshot.json'
$state = Join-Path $root 'picks/paper_trading_state.test.json'
$ledger = Join-Path $root 'picks/paper_trading_ledger.test.csv'

if (-not (Test-Path $simulator)) {
  throw "Missing simulator script: $simulator"
}
if (-not (Test-Path $rules)) {
  throw "Missing rules file: $rules"
}
if (-not (Test-Path $prices)) {
  throw "Missing price snapshot: $prices"
}

# Count active positions from rules to set dynamic expectations
$rulesJson = Get-Content -Path $rules -Raw -Encoding UTF8 | ConvertFrom-Json
$activePositions = @($rulesJson.positions | Where-Object { $_.status -eq 'active' })
$activeCount = $activePositions.Count

$entryPrices = Join-Path $root 'picks/paper_price_snapshot.entry.test.json'
$entryPricesObj = @{
  date = '2026-05-13T09:30:00+09:00'
  source = 'entry scenario'
  prices = @{}
}
foreach ($pos in $activePositions) {
  # Use a price within entry range to trigger BUY
  $entryPricesObj.prices[$pos.ticker] = $pos.entry_low
}
$entryPricesObj | ConvertTo-Json -Depth 5 | Set-Content -Path $entryPrices -Encoding UTF8

Remove-Item -Path $state -ErrorAction SilentlyContinue
Remove-Item -Path $ledger -ErrorAction SilentlyContinue

$output = & $simulator -RulesPath $rules -PricesPath $entryPrices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($exitCode -ne 0) {
  throw "Simulator failed with exit code $exitCode`n$($output -join "`n")"
}

if (-not (Test-Path $state)) {
  throw 'Simulator did not create state file'
}
if (-not (Test-Path $ledger)) {
  throw 'Simulator did not create ledger file'
}

$stateJson = Get-Content -Path $state -Raw -Encoding UTF8 | ConvertFrom-Json
if ($stateJson.mode -ne 'paper') {
  throw 'State mode must be paper'
}
if ($stateJson.cash -le 0) {
  throw 'State cash should remain positive after sizing'
}

$ledgerText = Get-Content -Path $ledger -Raw -Encoding UTF8
foreach ($expected in @('timestamp,ticker,name,side,quantity,price,notional,reason', 'BUY')) {
  if ($ledgerText -notmatch $expected) {
    throw "Ledger missing expected text: $expected"
  }
}

$repeatOutput = & $simulator -RulesPath $rules -PricesPath $entryPrices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$repeatJson = ($repeatOutput -join "`n") | ConvertFrom-Json
if (@($repeatJson.orders | Where-Object action -eq 'BUY').Count -ne 0) {
  throw 'Simulator should not create duplicate BUY orders for already-held positions'
}

$targetPrices = Join-Path $root 'picks/paper_price_snapshot.target.test.json'
$targetPricesObj = @{
  date = '2026-05-13T15:30:00+09:00'
  source = 'target scenario'
  prices = @{}
}
foreach ($pos in $activePositions) {
  # Use a price above target to trigger SELL
  $targetPricesObj.prices[$pos.ticker] = $pos.target
}
$targetPricesObj | ConvertTo-Json -Depth 5 | Set-Content -Path $targetPrices -Encoding UTF8

$targetOutput = & $simulator -RulesPath $rules -PricesPath $targetPrices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$targetJson = ($targetOutput -join "`n") | ConvertFrom-Json
if (@($targetJson.orders | Where-Object { $_.action -eq 'SELL' -and $_.reason -eq 'target_hit' }).Count -ne $activeCount) {
  throw "Target scenario should create one target_hit SELL per open position (expected $activeCount)"
}

$secondTargetOutput = & $simulator -RulesPath $rules -PricesPath $targetPrices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$secondTargetJson = ($secondTargetOutput -join "`n") | ConvertFrom-Json
if (@($secondTargetJson.orders | Where-Object { $_.action -eq 'SELL' -and $_.reason -eq 'target_hit' }).Count -ne 0) {
  throw 'Simulator should not repeatedly sell the same target tier on the same price snapshot'
}

Write-Output 'paper trading tests passed'
