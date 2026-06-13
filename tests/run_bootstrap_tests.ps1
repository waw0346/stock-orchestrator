$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/bootstrap.py'

$jsonText = python $script --dry-run --json
if ($LASTEXITCODE -ne 0) {
  throw 'bootstrap.py dry-run failed'
}
$report = $jsonText | ConvertFrom-Json
if (-not $report.python.ok) {
  throw 'bootstrap.py reported unsupported Python version'
}
if (-not $report.requirements_present) {
  throw 'bootstrap.py did not find requirements.txt'
}
if (@($report.packages | Where-Object { $_.name -eq 'pydantic' }).Count -ne 1) {
  throw 'bootstrap.py should report pydantic requirement'
}

python (Join-Path $root 'tests/run_cross_platform_smoke.py')
if ($LASTEXITCODE -ne 0) {
  throw 'cross-platform smoke test failed'
}

Write-Output 'bootstrap tests passed'
