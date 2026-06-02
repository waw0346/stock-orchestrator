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
  'MCP config',
  'US close Korea preopen strategy',
  'Capital protection gate',
  'Summary'
)) {
  if ($text -notmatch [regex]::Escape($expected)) {
    throw "Validator output missing expected section: $expected`n$text"
  }
}

foreach ($expectedSource in @(
  'status mismatch',
  '.mcp.json',
  'CURRENT_STATE.md',
  'INVESTMENT_POLICY.md',
  'pre_trade_checklist.md',
  'market-regime-analyst.md',
  'portfolio-manager.md',
  'position-sizing-analyst.md',
  'performance-reviewer.md',
  'us-close-korea-strategist.md'
)) {
  $validatorText = Get-Content -Path $validator -Raw -Encoding UTF8
  if ($validatorText -notmatch [regex]::Escape($expectedSource)) {
    throw "Validator source missing risk-control assertion: $expectedSource"
  }
}

if ($text -match 'FAIL ') {
  throw "Validator emitted FAIL lines unexpectedly:`n$text"
}

Write-Output 'validation tests passed'
