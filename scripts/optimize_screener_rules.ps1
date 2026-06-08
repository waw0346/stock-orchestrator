param(
  [string]$IndexPath = '',
  [string]$MarketSnapshotPath = '',
  [string]$ConfigPath = '',
  [string]$ObsidianLogPath = ''
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/optimize_screener_rules.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($IndexPath)) {
  $argsList += @('--index-path', $IndexPath)
}
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($ConfigPath)) {
  $argsList += @('--config-path', $ConfigPath)
}
if (-not [string]::IsNullOrWhiteSpace($ObsidianLogPath)) {
  $argsList += @('--obsidian-log-path', $ObsidianLogPath)
}

python @argsList
exit $LASTEXITCODE
