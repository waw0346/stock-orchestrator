$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$reviewer = Join-Path $root 'scripts/review_changes.ps1'

if (-not (Test-Path $reviewer)) {
  throw "Missing change review script: $reviewer"
}

$output = & $reviewer -WarnOnly 2>&1
$text = $output -join "`n"
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }

if ($exitCode -ne 0) {
  throw "Change reviewer should exit 0 with -WarnOnly, got $exitCode`n$text"
}

foreach ($expected in @(
  'Change review',
  'Change classification',
  'Archived file guard',
  'Pick risk guard',
  'Summary'
)) {
  if ($text -notmatch [regex]::Escape($expected)) {
    throw "Change reviewer output missing expected section: $expected`n$text"
  }
}

foreach ($expectedSource in @(
  'Capital Protection Gate',
  'ARCHIVED',
  'Unknown pick status',
  'missing from INDEX',
  'Local/transient file should not be committed',
  'scripts/lib',
  'paper_price_snapshot\.json',
  'run_all_tests'
)) {
  $reviewerText = Get-Content -Path $reviewer -Raw -Encoding UTF8
  if ($reviewerText -notmatch [regex]::Escape($expectedSource)) {
    throw "Change reviewer source missing assertion: $expectedSource"
  }
}

Write-Output 'change review tests passed'
