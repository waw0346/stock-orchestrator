$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venvScripts = if ($IsLinux -or $IsMacOS) {
  Join-Path $root '.venv/bin'
} else {
  Join-Path $root '.venv/Scripts'
}
$venvPython = if ($IsLinux -or $IsMacOS) {
  Join-Path $venvScripts 'python'
} else {
  Join-Path $venvScripts 'python.exe'
}
if (Test-Path $venvPython) {
  $pathSeparator = [string][IO.Path]::PathSeparator
  $pathParts = @($env:Path -split [regex]::Escape($pathSeparator) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  if ($pathParts.Count -eq 0 -or $pathParts[0] -ne $venvScripts) {
    $env:Path = ($venvScripts + $pathSeparator + $env:Path)
  }
}

$powerShellCommand = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $powerShellCommand) {
  $powerShellCommand = Get-Command powershell -ErrorAction SilentlyContinue
}
if ($null -eq $powerShellCommand) {
  throw 'PowerShell is required for the full validation suite. Run python tests/run_cross_platform_smoke.py for portable smoke checks.'
}

$checks = @(
  @{ Name = 'project validation'; Path = 'scripts/validate_project.ps1' },
  @{ Name = 'change review'; Path = 'scripts/review_changes.ps1' },
  @{ Name = 'validation tests'; Path = 'tests/run_validation_tests.ps1' },
  @{ Name = 'change review tests'; Path = 'tests/run_change_review_tests.ps1' },
  @{ Name = 'bootstrap tests'; Path = 'tests/run_bootstrap_tests.ps1' },
  @{ Name = 'runtime contract tests'; Path = 'tests/run_runtime_contract_tests.ps1' },
  @{ Name = 'context summary tests'; Path = 'tests/run_context_summary_tests.ps1' },
  @{ Name = 'integration tests'; Path = 'tests/run_integration_tests.ps1' },
  @{ Name = 'kiwoom rest client tests'; Path = 'tests/run_kiwoom_rest_client_tests.ps1' },
  @{ Name = 'kiwoom foreign rank tests'; Path = 'tests/run_kiwoom_foreign_rank_tests.ps1' },
  @{ Name = 'market radar tests'; Path = 'tests/run_market_radar_tests.ps1' },
  @{ Name = 'paper trading tests'; Path = 'tests/run_paper_trading_tests.ps1' }
)

foreach ($check in $checks) {
  $path = Join-Path $root $check.Path
  if (-not (Test-Path $path)) {
    throw "Missing check: $($check.Name) at $($check.Path)"
  }

  Write-Output ("== {0} ==" -f $check.Name)
  & $powerShellCommand.Source -NoProfile -ExecutionPolicy Bypass -File $path
  if ($LASTEXITCODE -ne 0) {
    throw "Check failed: $($check.Name)"
  }
  Write-Output ''
}

Write-Output 'all tests passed'
