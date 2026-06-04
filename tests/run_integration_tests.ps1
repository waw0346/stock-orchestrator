$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Assert-FileContains {
  param(
    [string]$RelativePath,
    [string[]]$Patterns
  )

  $path = Join-Path $root $RelativePath
  if (-not (Test-Path $path)) {
    throw "Missing required file: $RelativePath"
  }

  $text = Get-Content -Path $path -Raw -Encoding UTF8
  foreach ($pattern in $Patterns) {
    if ($text -notmatch [regex]::Escape($pattern)) {
      throw "$RelativePath missing required text: $pattern"
    }
  }
}

Assert-FileContains '.claude/agents/flow-momentum-tracker.md' @(
  'name: flow-momentum-tracker',
  'picks/2026-05-12_flow_momentum_picks.md',
  'picks/tracking_weekly_cumulative_flow_momentum.md',
  'excluded_stop_loss'
)

Assert-FileContains '.claude/agents/entry-exit-timing-strategist.md' @(
  'name: entry-exit-timing-strategist',
  'Kelly-style sizing',
  'No direct trading instruction',
  'entry_zone',
  'exit_plan'
)

Assert-FileContains '.claude/agents/us-close-korea-strategist.md' @(
  'name: us-close-korea-strategist',
  'us-close-korea-strategist',
  'WATCHLIST.md',
  'preopen_candidates',
  'Hard Block'
)

Assert-FileContains 'picks/entry_exit_timing_playbook.md' @(
  'entry-exit-timing-strategist',
  '000660',
  '005930',
  '018260',
  'No direct trading instruction'
)

Assert-FileContains 'CLAUDE.md' @(
  'flow momentum weekly',
  '@flow-momentum-tracker',
  'entry exit timing',
  '@entry-exit-timing-strategist',
  '@us-close-korea-strategist'
)

Assert-FileContains 'README.md' @(
  'flow-momentum-tracker',
  'tracking_weekly_cumulative_flow_momentum.md',
  'entry-exit-timing-strategist',
  'us-close-korea-strategist'
)

Assert-FileContains 'scripts/validate_project.ps1' @(
  'Flow/Momentum tracking',
  'tracking_weekly_cumulative_flow_momentum.md',
  'Entry/Exit timing',
  'pullback_candidates.json',
  'US close Korea preopen strategy',
  'preopen_candidates.json',
  'preopen_filtered_candidates.json',
  'Paper trading',
  'Market data crawler',
  'Fundamentals collector',
  'Flow data collector',
  'Foreign streak scanner',
  'candidate_board.json',
  'Fiscal.ai integration'
)

Assert-FileContains 'docs/paper_trading_options.md' @(
  'KIS Developers',
  'KIS_ACCOUNT_TYPE=VIRTUAL',
  'paper_trade_simulator.ps1',
  'paper'
)

$pullbackOutput = Join-Path $root 'picks/cache/pullback_candidates.test.json'
Remove-Item -Path $pullbackOutput -ErrorAction SilentlyContinue

Assert-FileContains 'docs/pullback_screen.md' @(
  'pullback_candidates.json',
  '4-signal',
  'ENTRY'
)

$pullbackScreen = Join-Path $root 'scripts/run_pullback_screen.ps1'
$pullbackRun = & $pullbackScreen -OfflineSample -OutputPath $pullbackOutput 2>&1
$pullbackExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($pullbackExitCode -ne 0) {
  throw "Pullback screen offline sample failed with exit code $pullbackExitCode`n$($pullbackRun -join "`n")"
}
if (-not (Test-Path $pullbackOutput)) {
  throw 'Pullback screen did not create test candidates'
}
$pullbackJson = Get-Content -Path $pullbackOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $pullbackJson.candidates) {
  throw 'Pullback screen output missing candidates'
}
if (($pullbackJson.summary.strong_entry + $pullbackJson.summary.probe_entry) -lt 1) {
  throw 'Pullback screen offline sample should exercise an ENTRY screening state'
}

$usCloseOutput = Join-Path $root 'picks/cache/us_close_snapshot.test.json'
$preopenOutput = Join-Path $root 'picks/cache/preopen_candidates.test.json'
Remove-Item -Path $usCloseOutput -ErrorAction SilentlyContinue
Remove-Item -Path $preopenOutput -ErrorAction SilentlyContinue

Assert-FileContains 'docs/us_close_korea_preopen.md' @(
  'us_close_snapshot.json',
  'preopen_candidates.json',
  'preopen_filtered_candidates.json',
  'Capital Protection Gate'
)

$usCloseCollector = Join-Path $root 'scripts/collect_us_close_data.ps1'
$usCloseRun = & $usCloseCollector -OfflineSample -SnapshotPath $usCloseOutput -CandidatesPath $preopenOutput 2>&1
$usCloseExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($usCloseExitCode -ne 0) {
  throw "US close collector offline sample failed with exit code $usCloseExitCode`n$($usCloseRun -join "`n")"
}
if (-not (Test-Path $usCloseOutput)) {
  throw 'US close collector did not create test snapshot'
}
if (-not (Test-Path $preopenOutput)) {
  throw 'US close collector did not create preopen candidates'
}

$preopenJson = Get-Content -Path $preopenOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($preopenJson.preopen_candidates).Count -gt 3) {
  throw 'US close collector should create at most 3 preopen candidates'
}

$preopenFilteredOutput = Join-Path $root 'picks/cache/preopen_filtered_candidates.test.json'
Remove-Item -Path $preopenFilteredOutput -ErrorAction SilentlyContinue

$preopenFilter = Join-Path $root 'scripts/run_preopen_filter.ps1'
$preopenFilterRun = & $preopenFilter -OfflineSample -CandidatesPath $preopenOutput -OutputPath $preopenFilteredOutput 2>&1
$preopenFilterExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($preopenFilterExitCode -ne 0) {
  throw "Preopen filter offline sample failed with exit code $preopenFilterExitCode`n$($preopenFilterRun -join "`n")"
}
if (-not (Test-Path $preopenFilteredOutput)) {
  throw 'Preopen filter did not create filtered candidates'
}
$preopenFilteredJson = Get-Content -Path $preopenFilteredOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($preopenFilteredJson.final_candidates).Count -gt 3) {
  throw 'Preopen filter should create at most 3 final candidates'
}

$crawlerOutput = Join-Path $root 'picks/cache/market_data_snapshot.test.json'
$crawlerUniverseOutput = Join-Path $root 'picks/cache/market_data_snapshot.universe.test.json'
$paperOutput = Join-Path $root 'picks/paper_price_snapshot.crawler.test.json'
Remove-Item -Path $crawlerOutput -ErrorAction SilentlyContinue
Remove-Item -Path $crawlerUniverseOutput -ErrorAction SilentlyContinue
Remove-Item -Path $paperOutput -ErrorAction SilentlyContinue

Assert-FileContains 'docs/market_data_crawler.md' @(
  'JSON',
  'TOSS_INVEST_TOKEN',
  'market_data_snapshot.json',
  'technical',
  'rsi14',
  'AllowPartialWrite',
  'UpdatePaperPriceSnapshot'
)

$crawler = Join-Path $root 'scripts/collect_market_data.ps1'
$output = & $crawler -Tickers '005930,000660' -SnapshotPath $crawlerOutput -PaperPricePath $paperOutput -OfflineSample -UpdatePaperPriceSnapshot 2>&1
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($exitCode -ne 0) {
  throw "Market data crawler offline sample failed with exit code $exitCode`n$($output -join "`n")"
}
if (-not (Test-Path $crawlerOutput)) {
  throw 'Market data crawler did not create test market data snapshot'
}
if (-not (Test-Path $paperOutput)) {
  throw 'Market data crawler did not create test paper price snapshot'
}
$crawlerJson = Get-Content -Path $crawlerOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $crawlerJson.items[0].technical.ma20 -or $null -eq $crawlerJson.items[0].technical.rsi14) {
  throw 'Market data crawler offline sample missing technical indicators'
}
if ($null -eq $crawlerJson.items[0].volume) {
  throw 'Market data crawler offline sample missing current volume'
}

$universeRun = & $crawler -SnapshotPath $crawlerUniverseOutput -OfflineSample 2>&1
$universeExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($universeExitCode -ne 0) {
  throw "Market data crawler universe offline sample failed with exit code $universeExitCode`n$($universeRun -join "`n")"
}
$universeJson = Get-Content -Path $crawlerUniverseOutput -Raw -Encoding UTF8 | ConvertFrom-Json
$universeTickers = @($universeJson.items | ForEach-Object { $_.ticker })
if ($universeTickers -notcontains '240810') {
  throw 'Market data crawler universe should include preopen candidate 240810'
}

$flowOutput = Join-Path $root 'picks/cache/flow_snapshot.test.json'
$flowMarketOutput = Join-Path $root 'picks/cache/market_data_snapshot.flow.test.json'
Remove-Item -Path $flowOutput -ErrorAction SilentlyContinue
Copy-Item -Path $crawlerUniverseOutput -Destination $flowMarketOutput -Force

Assert-FileContains 'docs/flow_data_collector.md' @(
  'flow_snapshot.json',
  'foreign_net_buy_5d',
  'institution_net_buy_5d'
)

$flowCollector = Join-Path $root 'scripts/collect_flow_data.ps1'
$flowRun = & $flowCollector -MarketSnapshotPath $flowMarketOutput -SnapshotPath $flowOutput -OfflineSample -UpdateMarketSnapshot 2>&1
$flowExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($flowExitCode -ne 0) {
  throw "Flow data collector offline sample failed with exit code $flowExitCode`n$($flowRun -join "`n")"
}
if (-not (Test-Path $flowOutput)) {
  throw 'Flow data collector did not create flow snapshot'
}
$flowJson = Get-Content -Path $flowOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $flowJson.items[0].foreign_net_buy_5d -or $null -eq $flowJson.items[0].institution_net_buy_5d) {
  throw 'Flow data collector output missing 5-day flow fields'
}
$flowMarketJson = Get-Content -Path $flowMarketOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $flowMarketJson.items[0].flow.foreign_net_buy_5d) {
  throw 'Flow data collector did not merge flow into market snapshot'
}

$foreignFlowCsv = Join-Path $root 'picks/cache/foreign_flow_history.test.csv'
$foreignStreakOutput = Join-Path $root 'picks/cache/foreign_streak_candidates.test.json'
Remove-Item -Path $foreignFlowCsv -ErrorAction SilentlyContinue
Remove-Item -Path $foreignStreakOutput -ErrorAction SilentlyContinue
$foreignFlowRows = @(
  'date,ticker,name,foreign_net_buy,institution_net_buy,close,volume',
  '2026-06-01,005930,Samsung Electronics,12000000000,3000000000,340000,1000000',
  '2026-06-02,005930,Samsung Electronics,15000000000,4000000000,350000,1200000',
  '2026-06-03,005930,Samsung Electronics,18000000000,2000000000,355000,1100000',
  '2026-06-01,000660,SK Hynix,8000000000,1000000000,2200000,500000',
  '2026-06-02,000660,SK Hynix,-1000000000,2000000000,2250000,600000',
  '2026-06-03,000660,SK Hynix,9000000000,1000000000,2294000,550000',
  '2026-06-01,018260,Samsung SDS,7000000000,-1000000000,260000,400000',
  '2026-06-02,018260,Samsung SDS,8000000000,1000000000,268000,420000',
  '2026-06-03,018260,Samsung SDS,9000000000,2000000000,271000,450000'
)
$foreignFlowCsvText = [string]::Join([Environment]::NewLine, $foreignFlowRows)
Set-Content -Path $foreignFlowCsv -Value $foreignFlowCsvText -Encoding UTF8

Assert-FileContains 'docs/foreign_streak_scanner.md' @(
  'foreign_streak_candidates.json',
  'consecutive_foreign_buy_days',
  '3-day consecutive foreign net-buy'
)

$foreignStreakScanner = Join-Path $root 'scripts/find_foreign_streaks.ps1'
$foreignStreakRun = & $foreignStreakScanner -InputCsvPath $foreignFlowCsv -OutputPath $foreignStreakOutput -MinConsecutiveDays 3 -Top 2 2>&1
$foreignStreakExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($foreignStreakExitCode -ne 0) {
  $foreignStreakText = $foreignStreakRun -join [Environment]::NewLine
  throw "Foreign streak scanner failed with exit code $foreignStreakExitCode`n$foreignStreakText"
}
if (-not (Test-Path $foreignStreakOutput)) {
  throw 'Foreign streak scanner did not create output'
}
$foreignStreakJson = Get-Content -Path $foreignStreakOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($foreignStreakJson.candidates).Count -ne 2) {
  throw 'Foreign streak scanner should keep the requested top 2 candidates'
}
if ($foreignStreakJson.candidates[0].ticker -ne '005930') {
  throw 'Foreign streak scanner should rank highest cumulative foreign net buy first'
}
if ($foreignStreakJson.candidates.ticker -contains '000660') {
  throw 'Foreign streak scanner should exclude tickers without a 3-day foreign buy streak'
}
if ($foreignStreakJson.candidates[0].consecutive_foreign_buy_days -ne 3) {
  throw 'Foreign streak scanner should report consecutive foreign buy days'
}

$fundamentalsOutput = Join-Path $root 'picks/cache/fundamentals_snapshot.test.json'
$fundamentalsUniverseOutput = Join-Path $root 'picks/cache/fundamentals_snapshot.universe.test.json'
Remove-Item -Path $fundamentalsOutput -ErrorAction SilentlyContinue
Remove-Item -Path $fundamentalsUniverseOutput -ErrorAction SilentlyContinue

Assert-FileContains 'docs/fundamentals_collector.md' @(
  'OpenDART',
  'OPENDART_API_KEY',
  'Provider',
  'pykrx',
  'BPS',
  'PER',
  'PBR',
  'fundamentals_snapshot.json'
)

$fundamentals = Join-Path $root 'scripts/collect_fundamentals.ps1'
$fundamentalsRun = & $fundamentals -Provider offline_sample -Tickers '005930,000660' -Date '20260602' -SnapshotPath $fundamentalsOutput 2>&1
$fundamentalsExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($fundamentalsExitCode -ne 0) {
  throw "Fundamentals collector offline sample failed with exit code $fundamentalsExitCode`n$($fundamentalsRun -join "`n")"
}
if (-not (Test-Path $fundamentalsOutput)) {
  throw 'Fundamentals collector did not create test snapshot'
}

$fundamentalsUniverseRun = & $fundamentals -Provider offline_sample -Date '20260602' -SnapshotPath $fundamentalsUniverseOutput 2>&1
$fundamentalsUniverseExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($fundamentalsUniverseExitCode -ne 0) {
  throw "Fundamentals collector universe offline sample failed with exit code $fundamentalsUniverseExitCode`n$($fundamentalsUniverseRun -join "`n")"
}
$fundamentalsUniverseJson = Get-Content -Path $fundamentalsUniverseOutput -Raw -Encoding UTF8 | ConvertFrom-Json
$fundamentalsUniverseTickers = @($fundamentalsUniverseJson.items | ForEach-Object { $_.ticker })
if ($fundamentalsUniverseTickers -notcontains '240810') {
  throw 'Fundamentals collector universe should include preopen candidate 240810'
}
if ($fundamentalsUniverseTickers -notcontains '373220') {
  throw 'Fundamentals collector universe should include market snapshot candidate 373220'
}

$candidateBoardOutput = Join-Path $root 'picks/cache/candidate_board.test.json'
Remove-Item -Path $candidateBoardOutput -ErrorAction SilentlyContinue

Assert-FileContains 'docs/candidate_board.md' @(
  'candidate_board.json',
  'preopen',
  'pullback',
  'fundamentals'
)

Assert-FileContains 'docs/fiscal_ai_integration.md' @(
  'Fiscal.ai',
  'FISCAL_AI_API_KEY',
  'https://api.fiscal.ai/mcp',
  'check_fiscal_ai.ps1',
  'fiscal_ai_snapshot.json',
  'candidate_board.json'
)

$fiscalAiOutput = Join-Path $root 'picks/cache/fiscal_ai_snapshot.test.json'
Remove-Item -Path $fiscalAiOutput -ErrorAction SilentlyContinue

$fiscalAiCollector = Join-Path $root 'scripts/collect_fiscal_ai.ps1'
$fiscalAiRun = & $fiscalAiCollector -OfflineSample -CompanyKeys 'NASDAQ_MSFT,NASDAQ_NVDA' -SnapshotPath $fiscalAiOutput 2>&1
$fiscalAiExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($fiscalAiExitCode -ne 0) {
  throw "Fiscal.ai collector offline sample failed with exit code $fiscalAiExitCode`n$($fiscalAiRun -join "`n")"
}
if (-not (Test-Path $fiscalAiOutput)) {
  throw 'Fiscal.ai collector did not create snapshot'
}
$fiscalAiJson = Get-Content -Path $fiscalAiOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $fiscalAiJson.items -or @($fiscalAiJson.items).Count -ne 2) {
  throw 'Fiscal.ai collector snapshot missing items'
}
if ($fiscalAiJson.items[0].source -ne 'offline_fixture') {
  throw 'Fiscal.ai collector offline sample should use offline_fixture source'
}

$fiscalAiNewsOutput = Join-Path $root 'picks/cache/fiscal_ai_news.test.json'
Remove-Item -Path $fiscalAiNewsOutput -ErrorAction SilentlyContinue
$fiscalAiNewsRun = & $fiscalAiCollector -OfflineSample -CompanyNews -CompanyKeys 'NASDAQ_MSFT,NASDAQ_NVDA' -SnapshotPath $fiscalAiNewsOutput 2>&1
$fiscalAiNewsExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($fiscalAiNewsExitCode -ne 0) {
  throw "Fiscal.ai company-news offline sample failed with exit code $fiscalAiNewsExitCode`n$($fiscalAiNewsRun -join "`n")"
}
if (-not (Test-Path $fiscalAiNewsOutput)) {
  throw 'Fiscal.ai company-news collector did not create snapshot'
}
$fiscalAiNewsJson = Get-Content -Path $fiscalAiNewsOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($true -ne $fiscalAiNewsJson.company_news) {
  throw 'Fiscal.ai company-news snapshot missing company_news flag'
}
if (@($fiscalAiNewsJson.items).Count -lt 1) {
  throw 'Fiscal.ai company-news offline sample should include news items'
}
if ([string]::IsNullOrWhiteSpace($fiscalAiNewsJson.items[0].event_type)) {
  throw 'Fiscal.ai company-news item missing event_type'
}

$candidateBoard = Join-Path $root 'scripts/run_candidate_board.ps1'
$candidateBoardRun = & $candidateBoard -MarketSnapshotPath $flowMarketOutput -PullbackPath $pullbackOutput -PreopenFilteredPath $preopenFilteredOutput -FundamentalsPath $fundamentalsOutput -FiscalAiNewsPath $fiscalAiNewsOutput -OutputPath $candidateBoardOutput 2>&1
$candidateBoardExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
if ($candidateBoardExitCode -ne 0) {
  throw "Candidate board failed with exit code $candidateBoardExitCode`n$($candidateBoardRun -join "`n")"
}
if (-not (Test-Path $candidateBoardOutput)) {
  throw 'Candidate board did not create output'
}
$candidateBoardJson = Get-Content -Path $candidateBoardOutput -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $candidateBoardJson.rows -or @($candidateBoardJson.rows).Count -eq 0) {
  throw 'Candidate board output missing rows'
}
if ($null -eq $candidateBoardJson.rows[0].checks.fundamentals) {
  throw 'Candidate board output missing fundamentals check'
}
if ($null -eq $candidateBoardJson.us_catalysts -or @($candidateBoardJson.us_catalysts).Count -lt 1) {
  throw 'Candidate board output missing Fiscal.ai US catalysts'
}

Write-Output 'integration tests passed'
