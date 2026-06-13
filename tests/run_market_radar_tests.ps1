$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$runner = Join-Path $root 'scripts/run_market_radar.ps1'
$marketPath = Join-Path $root 'picks/cache/market_data_snapshot.radar.test.json'
$candidatePath = Join-Path $root 'picks/cache/candidate_board.radar.test.json'
$flowPath = Join-Path $root 'picks/cache/flow_snapshot.radar.test.json'
$newsPath = Join-Path $root 'picks/cache/fiscal_ai_news.radar.test.json'
$outputPath = Join-Path $root 'picks/cache/market_radar.radar.test.json'
$basisPath = Join-Path $root 'picks/cache/futures_basis.radar.test.jsonl'
$afterCloseOutputPath = Join-Path $root 'picks/cache/market_radar.after_close.test.json'

foreach ($path in @($marketPath, $candidatePath, $flowPath, $newsPath, $outputPath, $basisPath, $afterCloseOutputPath)) {
  Remove-Item -Path $path -ErrorAction SilentlyContinue
}

$market = @{
  generated_at = '2026-06-05T11:30:00+09:00'
  market = 'KR'
  mode = 'offline_test'
  items = @(
    @{
      ticker = '005930'
      name = 'Samsung Electronics'
      price = 343000
      change_rate = 2.4
      volume = 2400000
      technical = @{ volume_avg20 = 1000000; rsi14 = 54.2 }
      flow = @{ foreign_net_buy_5d = 12000000000; institution_net_buy_5d = 3500000000 }
    },
    @{
      ticker = '000660'
      name = 'SK Hynix'
      price = 2188000
      change_rate = 1.3
      volume = 780000
      technical = @{ volume_avg20 = 500000; rsi14 = 61.1 }
      flow = @{ foreign_net_buy_5d = 9000000000; institution_net_buy_5d = -1000000000 }
    },
    @{
      ticker = '454910'
      name = 'Doosan Robotics'
      price = 135900
      change_rate = -8.7
      volume = 1726406
      technical = @{ volume_avg20 = 700000; rsi14 = 58.3 }
      flow = @{ foreign_net_buy_5d = -2000000000; institution_net_buy_5d = 800000000 }
    },
    @{
      ticker = '012450'
      name = 'Hanwha Aerospace'
      price = 1048000
      change_rate = -1.8
      volume = 320000
      technical = @{ volume_avg20 = 250000; rsi14 = 31.0 }
      flow = @{ foreign_net_buy_5d = 500000000; institution_net_buy_5d = 4500000000 }
    }
  )
}
$market | ConvertTo-Json -Depth 8 | Set-Content -Path $marketPath -Encoding UTF8

$candidate = @{
  generated_at = '2026-06-05T11:32:00+09:00'
  rows = @(
    @{ ticker = '005930'; name = 'Samsung Electronics'; decision = 'PASS'; score = 3 },
    @{ ticker = '000660'; name = 'SK Hynix'; decision = 'BLOCK'; score = 3 },
    @{ ticker = '454910'; name = 'Doosan Robotics'; decision = 'PASS'; score = 3 },
    @{ ticker = '012450'; name = 'Hanwha Aerospace'; decision = 'WATCH'; score = 4 }
  )
}
$candidate | ConvertTo-Json -Depth 8 | Set-Content -Path $candidatePath -Encoding UTF8

$flow = @{
  generated_at = '2026-06-05T11:31:00+09:00'
  provider = 'offline_test'
  items = @(
    @{ ticker = '005930'; foreign_net_buy_5d = 12000000000; institution_net_buy_5d = 3500000000 },
    @{ ticker = '000660'; foreign_net_buy_5d = 9000000000; institution_net_buy_5d = -1000000000 },
    @{ ticker = '012450'; foreign_net_buy_5d = 500000000; institution_net_buy_5d = 4500000000 }
  )
}
$flow | ConvertTo-Json -Depth 8 | Set-Content -Path $flowPath -Encoding UTF8

$news = @{
  generated_at = '2026-06-05T11:31:30+09:00'
  items = @(
    @{ company_key = 'NASDAQ_NVDA'; event_type = 'product_launch'; importance = 3; title = 'NVIDIA expands physical AI platform'; collected_at = '2026-06-05T01:00:00Z' },
    @{ company_key = 'NASDAQ_AVGO'; event_type = 'earnings'; importance = 3; title = 'Broadcom AI semiconductor revenue jumps'; collected_at = '2026-06-05T00:30:00Z' }
  )
}
$news | ConvertTo-Json -Depth 8 | Set-Content -Path $newsPath -Encoding UTF8
@(
  '{"timestamp":"2026-06-05 15:00:00","basis":-1.1}',
  '{"timestamp":"2026-06-05 15:01:00","basis":-2.2}',
  '{"timestamp":"2026-06-05 15:02:00","basis":-2.6}'
) | Set-Content -Path $basisPath -Encoding UTF8

if (-not (Test-Path $runner)) {
  throw "Missing market radar runner: $runner"
}

$run = & $runner -MarketSnapshotPath $marketPath -CandidateBoardPath $candidatePath -FlowSnapshotPath $flowPath -FiscalAiNewsPath $newsPath -OutputPath $outputPath -Mode intraday 2>&1
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($exitCode -ne 0) {
  throw "Market radar failed with exit code $exitCode`n$($run -join "`n")"
}
if (-not (Test-Path $outputPath)) {
  throw 'Market radar did not create output'
}

$radar = Get-Content -Path $outputPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($section in @('preopen', 'intraday', 'after_close')) {
  if ($null -eq $radar.$section) {
    throw "Market radar output missing section: $section"
  }
}
if ($radar.note -notmatch 'not direct trading instructions') {
  throw 'Market radar should state that outputs are not direct trading instructions'
}
if (@($radar.theme_flows).Count -lt 2) {
  throw 'Market radar should classify at least two theme flows'
}
if (@($radar.theme_flows | Where-Object { $_.theme -eq 'AI semiconductor' }).Count -lt 1) {
  throw 'Market radar should detect AI semiconductor theme flow'
}
if (@($radar.intraday.alerts | Where-Object { $_.signal -eq 'THEME_ACTIVE' }).Count -lt 1) {
  throw 'Market radar should emit THEME_ACTIVE when a theme has broad positive flow'
}
if (@($radar.intraday.alerts | Where-Object { $_.signal -eq 'RISK_DOWN' }).Count -lt 1) {
  throw 'Market radar should emit RISK_DOWN for sharp negative moves'
}
foreach ($field in @('futures', 'etf', 'fx_rates', 'big_money')) {
  if ($null -eq $radar.market_context.$field) {
    throw "Market radar market_context missing $field watch block"
  }
}
if (@($radar.obsi.evidence_map | Where-Object { $_.evidence_type -eq 'artifact' }).Count -lt 1) {
  throw 'Market radar should include Obsidian artifact evidence mapping'
}
if (@($radar.obsi.evidence_map | Where-Object { $_.evidence_type -eq 'research_fact' }).Count -lt 1) {
  throw 'Market radar should include Obsidian research_fact evidence mapping'
}

$afterCloseRun = & $runner -MarketSnapshotPath $marketPath -CandidateBoardPath $candidatePath -FlowSnapshotPath $flowPath -FiscalAiNewsPath $newsPath -BasisLogPath $basisPath -OutputPath $afterCloseOutputPath -Mode after_close 2>&1
$afterCloseExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($afterCloseExitCode -ne 0) {
  throw "Market radar after-close failed with exit code $afterCloseExitCode`n$($afterCloseRun -join "`n")"
}
$afterCloseRadar = Get-Content -Path $afterCloseOutputPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($afterCloseRadar.market_context.futures.analysis.tick_count -ne 3) {
  throw 'Market radar after-close should read JSONL basis ticks'
}
if ($afterCloseRadar.market_context.futures.analysis.risk_level -ne 'HIGH') {
  throw 'Market radar after-close should preserve basis risk assessment'
}

Write-Output 'market radar tests passed'
