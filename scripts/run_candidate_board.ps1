param(
  [string]$MarketSnapshotPath = '',
  [string]$PullbackPath = '',
  [string]$PreopenFilteredPath = '',
  [string]$FundamentalsPath = '',
  [string]$FiscalAiNewsPath = '',
  [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/run_candidate_board.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($PullbackPath)) {
  $argsList += @('--pullback-path', $PullbackPath)
}
if (-not [string]::IsNullOrWhiteSpace($PreopenFilteredPath)) {
  $argsList += @('--preopen-filtered-path', $PreopenFilteredPath)
}
if (-not [string]::IsNullOrWhiteSpace($FundamentalsPath)) {
  $argsList += @('--fundamentals-path', $FundamentalsPath)
}
if (-not [string]::IsNullOrWhiteSpace($FiscalAiNewsPath)) {
  $argsList += @('--fiscal-ai-news-path', $FiscalAiNewsPath)
}
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $argsList += @('--output-path', $OutputPath)
}

python @argsList
exit $LASTEXITCODE
