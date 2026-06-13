param(
  [string]$MarketSnapshotPath = '',
  [string]$CandidateBoardPath = '',
  [string]$FlowSnapshotPath = '',
  [string]$FiscalAiNewsPath = '',
  [string]$BasisLogPath = '',
  [string]$OutputPath = '',
  [ValidateSet('preopen', 'intraday', 'after_close')]
  [string]$Mode = 'intraday'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/run_market_radar.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($CandidateBoardPath)) {
  $argsList += @('--candidate-board-path', $CandidateBoardPath)
}
if (-not [string]::IsNullOrWhiteSpace($FlowSnapshotPath)) {
  $argsList += @('--flow-snapshot-path', $FlowSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($FiscalAiNewsPath)) {
  $argsList += @('--fiscal-ai-news-path', $FiscalAiNewsPath)
}
if (-not [string]::IsNullOrWhiteSpace($BasisLogPath)) {
  $argsList += @('--basis-log-path', $BasisLogPath)
}
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $argsList += @('--output-path', $OutputPath)
}
$argsList += @('--mode', $Mode)

$oldPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
python @argsList
$ErrorActionPreference = $oldPreference
exit $LASTEXITCODE
