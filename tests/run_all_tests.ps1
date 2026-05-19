$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$checks = @(
  @{ Name = 'project validation'; Path = 'scripts/validate_project.ps1' },
  @{ Name = 'change review'; Path = 'scripts/review_changes.ps1' },
  @{ Name = 'validation tests'; Path = 'tests/run_validation_tests.ps1' },
  @{ Name = 'change review tests'; Path = 'tests/run_change_review_tests.ps1' },
  @{ Name = 'integration tests'; Path = 'tests/run_integration_tests.ps1' },
  @{ Name = 'paper trading tests'; Path = 'tests/run_paper_trading_tests.ps1' }
)

foreach ($check in $checks) {
  $path = Join-Path $root $check.Path
  if (-not (Test-Path $path)) {
    throw "Missing check: $($check.Name) at $($check.Path)"
  }

  Write-Output ("== {0} ==" -f $check.Name)
  & powershell -ExecutionPolicy Bypass -File $path
  if ($LASTEXITCODE -ne 0) {
    throw "Check failed: $($check.Name)"
  }
  Write-Output ''
}

Write-Output 'all tests passed'
