param(
  [string]$IndexPath = '',
  [string]$MarketSnapshotPath = '',
  [string]$OutputPath = '',
  [switch]$OfflineSample
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/run_pullback_screen.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($IndexPath)) {
  $argsList += @('--index-path', $IndexPath)
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

$oldPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
python @argsList
$ErrorActionPreference = $oldPreference
exit $LASTEXITCODE
