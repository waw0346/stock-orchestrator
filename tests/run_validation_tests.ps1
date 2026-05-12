$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$validator = Join-Path $root 'scripts/validate_project.ps1'

if (-not (Test-Path $validator)) {
  throw "Missing validator script: $validator"
}

$output = & $validator -WarnOnly 2>&1
$text = $output -join "`n"
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }

if ($exitCode -ne 0) {
  throw "Validator should exit 0 with -WarnOnly, got $exitCode`n$text"
}

foreach ($expected in @(
  'Local time',
  'Market session',
  'Agent JSON contract',
  'Pick data quality',
  'Summary'
)) {
  if ($text -notmatch [regex]::Escape($expected)) {
    throw "Validator output missing expected section: $expected`n$text"
  }
}

Write-Output 'validation tests passed'
