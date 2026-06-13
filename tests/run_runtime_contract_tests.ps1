$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/check_runtime_contract.py'

if (-not (Test-Path $script)) {
  throw 'Missing check_runtime_contract.py'
}

$jsonText = python $script --json
if ($LASTEXITCODE -ne 0) {
  throw 'check_runtime_contract.py failed'
}

$report = $jsonText | ConvertFrom-Json
if (-not $report.ok) {
  throw ("runtime contract check reported errors: {0}" -f (($report.errors | ForEach-Object { $_ }) -join '; '))
}
if (@($report.required_files | Where-Object { $_ -eq 'AGENTS.md' }).Count -ne 1) {
  throw 'runtime contract check should include AGENTS.md'
}
if (@($report.contracts_checked | Where-Object { $_ -eq 'CLAUDE.md' }).Count -ne 1) {
  throw 'runtime contract check should include CLAUDE.md'
}

Write-Output 'runtime contract tests passed'
