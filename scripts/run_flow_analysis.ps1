param(
  [string]$OutputPath = '',
  [switch]$OfflineSample,
  [int]$TopLimit = 100,
  [int]$ConsecutiveDays = 0
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/run_flow_analysis.py'
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
        # Clear mock/invalid token to force fresh token generation
        if ($key -eq 'KIWOOM_ACCESS_TOKEN' -and $val -eq 'au10001') {
          $val = ''
        }
        [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
      }
    }
  }
}

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $argsList += @('--output-path', $OutputPath)
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}
$argsList += @('--top-limit', [string]$TopLimit)
if ($ConsecutiveDays -gt 0) {
  $argsList += @('--consecutive-days', [string]$ConsecutiveDays)
}

python @argsList
exit $LASTEXITCODE
