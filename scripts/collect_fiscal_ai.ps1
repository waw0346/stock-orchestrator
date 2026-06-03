param(
  [string]$CompanyKeys = 'NASDAQ_MSFT,NASDAQ_NVDA,NASDAQ_AAPL',
  [string]$SnapshotPath = '',
  [string]$EnvFile = '',
  [int]$Timeout = 20,
  [switch]$ListCompanies,
  [switch]$TopNews,
  [switch]$CompanyNews,
  [string]$EventTypes = '',
  [int]$MinImportance = 1,
  [int]$MaxImportance = 3,
  [int]$PageNumber = 1,
  [int]$PageSize = 25,
  [switch]$OfflineSample
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/collect_fiscal_ai.py'

$argsList = @($script, '--company-keys', $CompanyKeys, '--timeout', [string]$Timeout)
if (-not [string]::IsNullOrWhiteSpace($SnapshotPath)) {
  $argsList += @('--snapshot-path', $SnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($EnvFile)) {
  $argsList += @('--env-file', $EnvFile)
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}
if ($ListCompanies) {
  $argsList += @('--list-companies', '--page-number', [string]$PageNumber, '--page-size', [string]$PageSize)
}
if ($TopNews) {
  $argsList += @('--top-news', '--page-size', [string]$PageSize, '--min-importance', [string]$MinImportance, '--max-importance', [string]$MaxImportance)
  if (-not [string]::IsNullOrWhiteSpace($EventTypes)) {
    $argsList += @('--event-types', $EventTypes)
  }
}
if ($CompanyNews) {
  $argsList += @('--company-news', '--page-size', [string]$PageSize)
}

python @argsList
exit $LASTEXITCODE
