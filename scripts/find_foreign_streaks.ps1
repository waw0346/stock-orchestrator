param(
  [string]$InputCsvPath = '',
  [string]$OutputPath = '',
  [int]$MinConsecutiveDays = 3,
  [int]$LookbackDays = 5,
  [int]$Top = 20
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/find_foreign_streaks.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($InputCsvPath)) {
  $argsList += @('--input-csv-path', $InputCsvPath)
}
if (-not [string]::IsNullOrWhiteSpace($OutputPath)) {
  $argsList += @('--output-path', $OutputPath)
}
$argsList += @('--min-consecutive-days', [string]$MinConsecutiveDays)
$argsList += @('--lookback-days', [string]$LookbackDays)
$argsList += @('--top', [string]$Top)

python @argsList
exit $LASTEXITCODE
