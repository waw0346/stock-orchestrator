param(
  [string]$MarketSnapshotPath = '',
  [string]$SnapshotPath = '',
  [string]$Tickers = '',
  [string]$Date = '',
  [string]$StartDate = '',
  [switch]$OfflineSample,
  [switch]$UpdateMarketSnapshot
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/collect_flow_data.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($SnapshotPath)) {
  $argsList += @('--snapshot-path', $SnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($Tickers)) {
  $argsList += @('--tickers', $Tickers)
}
if (-not [string]::IsNullOrWhiteSpace($Date)) {
  $argsList += @('--date', $Date)
}
if (-not [string]::IsNullOrWhiteSpace($StartDate)) {
  $argsList += @('--start-date', $StartDate)
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}
if ($UpdateMarketSnapshot) {
  $argsList += '--update-market-snapshot'
}

python @argsList
exit $LASTEXITCODE
