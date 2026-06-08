param(
  [string]$MarketSnapshotPath = '',
  [string]$FlowStreakPath = '',
  [string]$ForeignStreakPath = '',
  [string]$OutputPath = '',
  [string]$ObsidianNotePath = '',
  [double]$BreakoutRatio = 0.0,
  [double]$ContractionRatio = 0.0,
  [switch]$OfflineSample
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/run_flow_volume_filter.py'
$envFile = Join-Path $root '.env.local'

# Load Kiwoom environment variables from .env.local if present
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
      $parts = $line.Split('=', 2)
      $key = $parts[0].Trim()
      $val = $parts[1].Trim().Trim('"').Trim("'")
      if ($key.StartsWith('KIWOOM_')) {
        if ($key -eq 'KIWOOM_ACCESS_TOKEN' -and $val -eq 'au10001') {
          $val = ''
        }
        [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
      }
    }
  }
}

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($MarketSnapshotPath)) {
  $argsList += @('--market-snapshot-path', $MarketSnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($FlowStreakPath)) {
  $argsList += @('--flow-streak-path', $FlowStreakPath)
}
if (-not [string]::IsNullOrWhiteSpace($ForeignStreakPath)) {
  $argsList += @('--foreign-streak-path', $ForeignStreakPath)
}
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $argsList += @('--output-path', $OutputPath)
}
if (-not [string]::IsNullOrWhiteSpace($ObsidianNotePath)) {
  $argsList += @('--obsidian-note-path', $ObsidianNotePath)
}
if ($BreakoutRatio -gt 0.0) {
  $argsList += @('--breakout-ratio', [string]$BreakoutRatio)
}
if ($ContractionRatio -gt 0.0) {
  $argsList += @('--contraction-ratio', [string]$ContractionRatio)
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}

python @argsList
exit $LASTEXITCODE
