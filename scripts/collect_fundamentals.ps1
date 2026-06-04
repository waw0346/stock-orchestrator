param(
  [string]$Tickers = '',
  [string]$Date = '',
  [ValidateSet('opendart', 'pykrx', 'offline_sample')]
  [string]$Provider = 'opendart',
  [string]$Market = 'ALL',
  [string]$BusinessYear = '',
  [ValidateSet('11013', '11012', '11014', '11011')]
  [string]$ReportCode = '11011',
  [string]$SnapshotPath = '',
  [string]$MarketSnapshotPath = '',
  [string]$PreopenCandidatesPath = '',
  [switch]$RefreshCorpCodes,
  [switch]$OfflineSample,
  [switch]$SkipEnrich
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/collect_fundamentals.py'

$argsList = @($script, '--provider', $Provider, '--market', $Market, '--report-code', $ReportCode)
if (-not [string]::IsNullOrWhiteSpace($Tickers)) {
  $argsList += @('--tickers', $Tickers)
}
if (-not [string]::IsNullOrWhiteSpace($Date)) {
  $argsList += @('--date', $Date)
}
if (-not [string]::IsNullOrWhiteSpace($BusinessYear)) {
  $argsList += @('--business-year', $BusinessYear)
}
if (-not [string]::IsNullOrWhiteSpace($SnapshotPath)) {
  $argsList += @('--snapshot-path', $SnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($PreopenCandidatesPath)) {
  $argsList += @('--preopen-candidates-path', $PreopenCandidatesPath)
}
if ($RefreshCorpCodes) {
  $argsList += '--refresh-corp-codes'
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}
if ($SkipEnrich) {
  $argsList += '--skip-enrich'
}

python @argsList
exit $LASTEXITCODE
