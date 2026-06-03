param(
  [string]$CandidatesPath = '',
  [string]$MarketSnapshotPath = '',
  [string]$OutputPath = '',
  [switch]$OfflineSample,
  [switch]$AllowForeignUnknown
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/run_preopen_filter.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($CandidatesPath)) {
  $argsList += @('--candidates-path', $CandidatesPath)
}
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $argsList += @('--output-path', $OutputPath)
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}
if ($AllowForeignUnknown) {
  $argsList += '--allow-foreign-unknown'
}

python @argsList
exit $LASTEXITCODE
