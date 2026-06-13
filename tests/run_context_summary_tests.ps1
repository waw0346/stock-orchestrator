$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/summarize_context.py'

if (-not (Test-Path $script)) {
  throw 'Missing summarize_context.py'
}

$jsonText = python $script --ticker 012450 --purpose risk --max-items 2 --max-chars 1200
if ($LASTEXITCODE -ne 0) {
  throw 'summarize_context.py failed'
}

$summary = $jsonText | ConvertFrom-Json
if ($summary.ticker -ne '012450') {
  throw 'Context summary ticker mismatch'
}
if ($summary.purpose -ne 'risk') {
  throw 'Context summary purpose mismatch'
}
if ($null -eq $summary.token_control) {
  throw 'Context summary missing token_control block'
}
if (@($summary.index_rows).Count -lt 1) {
  throw 'Context summary should include INDEX.md row for 012450'
}
if ($null -eq $summary.pick_file -or [string]::IsNullOrWhiteSpace($summary.pick_file.excerpt)) {
  throw 'Context summary should include a compact pick file excerpt'
}

$outputPath = Join-Path $root 'picks/cache/context_summary.test.json'
Remove-Item -Path $outputPath -ErrorAction SilentlyContinue
python $script --ticker 012450 --purpose flow --max-items 1 --output-path $outputPath
if ($LASTEXITCODE -ne 0) {
  throw 'summarize_context.py file output failed'
}
if (-not (Test-Path $outputPath)) {
  throw 'Context summary did not create output file'
}

Write-Output 'context summary tests passed'
