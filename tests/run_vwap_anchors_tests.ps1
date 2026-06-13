$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/generate_vwap_anchors.py'
$outputPath = Join-Path $root 'picks/cache/vwap_anchors.test.json'
$missingSnapshot = Join-Path $root 'picks/cache/missing_market_data_snapshot.test.json'

Remove-Item -Path $outputPath -ErrorAction SilentlyContinue

python $script --snapshot-path $missingSnapshot --output-path $outputPath --base-date 2026-06-12
if ($LASTEXITCODE -ne 0) {
  throw 'generate_vwap_anchors.py offline run failed'
}
if (-not (Test-Path $outputPath)) {
  throw 'generate_vwap_anchors.py did not create test output'
}

$json = Get-Content -Path $outputPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($json.base_date -ne '2026-06-12') {
  throw 'vwap anchors test output used unexpected base_date'
}
if ($json.live_lookup_enabled) {
  throw 'vwap anchors should not enable live lookup by default'
}
if ($null -eq $json.tickers.'066570'.close_baseline) {
  throw 'vwap anchors output missing LG전자 baseline'
}
if ($null -eq $json.tickers.GLW.close_baseline) {
  throw 'vwap anchors output missing GLW baseline'
}

Remove-Item -Path $outputPath -ErrorAction SilentlyContinue
Write-Output 'vwap anchors tests passed'
