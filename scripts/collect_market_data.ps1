param(
  [string]$Tickers = '',
  [string]$SnapshotPath = '',
  [string]$PaperPricePath = '',
  [string]$PreopenCandidatesPath = '',
  [switch]$UpdatePaperPriceSnapshot,
  [switch]$OfflineSample,
  [switch]$IncludeTossPublic,
  [switch]$AllowPartialWrite,
  [int]$HistoryPages = -1
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/collect_market_data.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($Tickers)) {
  $argsList += @('--tickers', $Tickers)
}
if (-not [string]::IsNullOrWhiteSpace($SnapshotPath)) {
  $argsList += @('--snapshot-path', $SnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($PaperPricePath)) {
  $argsList += @('--paper-price-path', $PaperPricePath)
}
if (-not [string]::IsNullOrWhiteSpace($PreopenCandidatesPath)) {
  $argsList += @('--preopen-candidates-path', $PreopenCandidatesPath)
}
if ($UpdatePaperPriceSnapshot) {
  $argsList += '--update-paper-price-snapshot'
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}
if ($IncludeTossPublic) {
  $argsList += '--include-toss-public'
}
if ($AllowPartialWrite) {
  $argsList += '--allow-partial-write'
}
if ($HistoryPages -ge 0) {
  $argsList += @('--history-pages', [string]$HistoryPages)
}

python @argsList
exit $LASTEXITCODE
