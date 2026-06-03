param(
  [string]$CompanyKey = 'NASDAQ_MSFT',
  [string]$EnvFile = '',
  [int]$Timeout = 20
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/check_fiscal_ai.py'

$argsList = @($script, '--company-key', $CompanyKey, '--timeout', [string]$Timeout)
if (-not [string]::IsNullOrWhiteSpace($EnvFile)) {
  $argsList += @('--env-file', $EnvFile)
}

python @argsList
exit $LASTEXITCODE
