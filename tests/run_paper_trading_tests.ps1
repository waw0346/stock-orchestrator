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

Remove-Item -Path $state -ErrorAction SilentlyContinue
Remove-Item -Path $ledger -ErrorAction SilentlyContinue

$output = & $simulator -RulesPath $rules -PricesPath $prices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
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

$repeatOutput = & $simulator -RulesPath $rules -PricesPath $prices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$repeatJson = ($repeatOutput -join "`n") | ConvertFrom-Json
if (@($repeatJson.orders | Where-Object action -eq 'BUY').Count -ne 0) {
  throw 'Simulator should not create duplicate BUY orders for already-held positions'
}

$targetPrices = Join-Path $root 'picks/paper_price_snapshot.target.test.json'
@'
{
  "date": "2026-05-13T15:30:00+09:00",
  "source": "target scenario",
  "prices": {
    "000660": 2160000,
    "005930": 330000,
    "018260": 200000
  }
}
'@ | Set-Content -Path $targetPrices -Encoding UTF8

$targetOutput = & $simulator -RulesPath $rules -PricesPath $targetPrices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$targetJson = ($targetOutput -join "`n") | ConvertFrom-Json
if (@($targetJson.orders | Where-Object { $_.action -eq 'SELL' -and $_.reason -eq 'target_hit' }).Count -ne 3) {
  throw 'Target scenario should create one target_hit SELL per open position'
}

$secondTargetOutput = & $simulator -RulesPath $rules -PricesPath $targetPrices -StatePath $state -LedgerPath $ledger -InitialCash 100000000 2>&1
$secondTargetJson = ($secondTargetOutput -join "`n") | ConvertFrom-Json
if (@($secondTargetJson.orders | Where-Object { $_.action -eq 'SELL' -and $_.reason -eq 'target_hit' }).Count -ne 0) {
  throw 'Simulator should not repeatedly sell the same target tier on the same price snapshot'
}

Write-Output 'paper trading tests passed'
