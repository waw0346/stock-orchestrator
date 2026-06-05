param(
  [string]$OutputCsvPath = '',
  [string]$SnapshotPath = '',
  [string]$Date = '',
  [int]$Days = 1,
  [int]$Top = 20,
  [string]$BaseUrl = '',
  [string]$AccessToken = '',
  [string]$AppKey = '',
  [string]$AppSecret = '',
  [string]$MarketType = '000',
  [string]$TradeType = '2',
  [string]$Period = '0',
  [string]$ExchangeType = '1',
  [switch]$OfflineSample
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/collect_kiwoom_foreign_rank.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($OutputCsvPath)) {
  $argsList += @('--output-csv-path', $OutputCsvPath)
}
if (-not [string]::IsNullOrWhiteSpace($SnapshotPath)) {
  $argsList += @('--snapshot-path', $SnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($Date)) {
  $argsList += @('--date', $Date)
}
$argsList += @('--days', [string]$Days)
$argsList += @('--top', [string]$Top)
if (-not [string]::IsNullOrWhiteSpace($BaseUrl)) {
  $argsList += @('--base-url', $BaseUrl)
}
if (-not [string]::IsNullOrWhiteSpace($AccessToken)) {
  $argsList += @('--access-token', $AccessToken)
}
if (-not [string]::IsNullOrWhiteSpace($AppKey)) {
  $argsList += @('--app-key', $AppKey)
}
if (-not [string]::IsNullOrWhiteSpace($AppSecret)) {
  $argsList += @('--app-secret', $AppSecret)
}
$argsList += @('--market-type', $MarketType)
$argsList += @('--trade-type', $TradeType)
$argsList += @('--period', $Period)
$argsList += @('--exchange-type', $ExchangeType)
if ($OfflineSample) {
  $argsList += '--offline-sample'
}

python @argsList
exit $LASTEXITCODE
