param(
  [switch]$WarnOnly
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$issues = New-Object System.Collections.Generic.List[object]

function Add-Issue {
  param(
    [string]$Level,
    [string]$Area,
    [string]$Message
  )

  $issues.Add([pscustomobject]@{
    Level = $Level
    Area = $Area
    Message = $Message
  }) | Out-Null
}

function Read-FrontMatter {
  param([string]$Path)

  $lines = Get-Content -Path $Path -Encoding UTF8
  if ($lines.Count -lt 3 -or $lines[0] -ne '---') {
    return @{}
  }

  $data = @{}
  for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -eq '---') {
      break
    }
    if ($lines[$i] -match '^([^:]+):\s*(.*)$') {
      $key = $matches[1].Trim()
      $value = $matches[2].Trim().Trim('"')
      $data[$key] = $value
    }
  }

  return $data
}

function Test-MarketSession {
  param([datetime]$Now)

  $isWeekday = $Now.DayOfWeek -notin @([DayOfWeek]::Saturday, [DayOfWeek]::Sunday)
  $open = Get-Date -Year $Now.Year -Month $Now.Month -Day $Now.Day -Hour 9 -Minute 0 -Second 0
  $close = Get-Date -Year $Now.Year -Month $Now.Month -Day $Now.Day -Hour 15 -Minute 30 -Second 0

  if (-not $isWeekday) {
    return 'KRX closed: weekend'
  }
  if ($Now -lt $open) {
    return 'KRX closed: before regular session 09:00 KST'
  }
  if ($Now -gt $close) {
    return 'KRX closed: after regular session 15:30 KST'
  }
  return 'KRX regular session open'
}

function Normalize-PickStatus {
  param([string]$Status)

  if ([string]::IsNullOrWhiteSpace($Status)) {
    return ''
  }
  if ($Status -match '^(active|watch|closed|completed)') {
    return $matches[1]
  }
  return $Status.Trim()
}

Write-Output '== Local time =='
$now = Get-Date
Write-Output ($now.ToString('yyyy-MM-dd HH:mm:ss K'))

Write-Output ''
Write-Output '== Market session =='
Write-Output (Test-MarketSession -Now $now)

Write-Output ''
Write-Output '== Agent JSON contract =='
$agentDir = Join-Path $root '.claude/agents'
$agentFiles = Get-ChildItem -Path $agentDir -Filter '*.md' | Where-Object {
  $_.BaseName -notin @(
    'weekly-tracker',
    'monthly-tracker',
    'flow-momentum-tracker',
    'entry-exit-timing-strategist',
    'us-close-korea-strategist',
    'market-regime-analyst',
    'portfolio-manager',
    'position-sizing-analyst',
    'performance-reviewer',
    'obsi'
  )
}

foreach ($agent in $agentFiles) {
  $text = Get-Content -Path $agent.FullName -Raw -Encoding UTF8
  $hasJsonContract = $text -match '"agent"' -and
    $text -match '"ticker"' -and
    $text -match '"data_date"' -and
    $text -match '"confidence"' -and
    $text -match '"signal"'

  if ($hasJsonContract) {
    Write-Output ("OK   {0}" -f $agent.Name)
  } else {
    Add-Issue -Level 'ERROR' -Area 'Agent JSON contract' -Message ("Missing required JSON output contract: {0}" -f $agent.Name)
    Write-Output ("FAIL {0} - missing required JSON output contract" -f $agent.Name)
  }
}

Write-Output ''
Write-Output '== Obsidian record DB =='
$obsiAgent = Join-Path $root '.claude/agents/obsi.md'
$obsidianIndex = Join-Path $root 'obsidian/stock_log/Stock Orchestrator Index.md'
$gitignoreFile = Join-Path $root '.gitignore'

if (Test-Path $obsiAgent) {
  Write-Output ("OK   {0}" -f (Resolve-Path -Path $obsiAgent -Relative))
  $obsiText = Get-Content -Path $obsiAgent -Raw -Encoding UTF8
  foreach ($requiredText in @('name: obsi', 'Obsidian', 'git', 'stock_log', '07_stock_analysis', '08_error_reviews', '09_decision_journal', '11_calendar', '_templates', '_moc')) {
    if ($obsiText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Obsidian record DB' -Message ("obsi agent missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL obsi agent - missing {0}" -f $requiredText)
    }
  }
} else {
  Add-Issue -Level 'ERROR' -Area 'Obsidian record DB' -Message 'Missing .claude/agents/obsi.md'
  Write-Output 'FAIL .claude/agents/obsi.md - missing'
}

if (Test-Path $gitignoreFile) {
  $gitignoreText = Get-Content -Path $gitignoreFile -Raw -Encoding UTF8
  if ($gitignoreText -match '(?m)^obsidian/$') {
    Write-Output 'OK   .gitignore obsidian/'
  } else {
    Add-Issue -Level 'ERROR' -Area 'Obsidian record DB' -Message '.gitignore must exclude obsidian/'
    Write-Output 'FAIL .gitignore - missing obsidian/'
  }
}

if (Test-Path $obsidianIndex) {
  Write-Output 'OK   obsidian stock_log index'
} else {
  Add-Issue -Level 'WARN' -Area 'Obsidian record DB' -Message 'Missing local Obsidian stock_log index'
  Write-Output 'WARN obsidian stock_log index - missing'
}

foreach ($relative in @(
  'obsidian/stock_log/_moc/Obsidian Operating System Design.md',
  'obsidian/stock_log/_moc/Stock Analysis MOC.md',
  'obsidian/stock_log/_templates/Daily Log Template.md',
  'obsidian/stock_log/_templates/Execution Log Template.md',
  'obsidian/stock_log/_templates/Market News Template.md',
  'obsidian/stock_log/_templates/Candidate Board Template.md',
  'obsidian/stock_log/_templates/Stock Analysis Template.md',
  'obsidian/stock_log/_templates/Error Review Template.md',
  'obsidian/stock_log/_templates/Decision Journal Template.md',
  'obsidian/stock_log/_templates/Stock Calendar Day Template.md',
  'obsidian/stock_log/_templates/Stock Calendar Month Template.md',
  'obsidian/stock_log/_templates/Stock Calendar Year Template.md',
  'obsidian/stock_log/_moc/Stock Calendar MOC.md',
  'obsidian/stock_log/11_calendar/yearly/2026 Stock Calendar.md',
  'obsidian/stock_log/11_calendar/monthly/2026-06 Stock Calendar.md',
  'obsidian/stock_log/11_calendar/daily/2026-06-04 Stock Calendar.md'
)) {
  $path = Join-Path $root $relative
  if (Test-Path $path) {
    Write-Output ("OK   {0}" -f $relative)
  } else {
    Add-Issue -Level 'WARN' -Area 'Obsidian record DB' -Message ("Missing local Obsidian design/template file: {0}" -f $relative)
    Write-Output ("WARN {0} - missing" -f $relative)
  }
}

Write-Output ''
Write-Output '== Pick data quality =='
$pickDir = Join-Path $root 'picks'
$indexStatusByTicker = @{}
$indexFile = Join-Path $pickDir 'INDEX.md'
if (Test-Path $indexFile) {
  $indexLines = Get-Content -Path $indexFile -Encoding UTF8
  $section = ''
  foreach ($line in $indexLines) {
    if ($line -match '^##\s+Tracked') {
      $section = 'tracked'
      continue
    }
    if ($line -match '^##\s+Completed') {
      $section = 'completed'
      continue
    }
    if ($line -match '^##\s+Closed') {
      $section = 'closed'
      continue
    }
    if ($line -match '^##\s+') {
      $section = ''
      continue
    }

    if ($line -match '^\|\s*(20\d{2}-\d{2}-\d{2})\s*\|\s*([0-9]{6})\s*\|') {
      $columns = $line -split '\|'
      if ($columns.Count -ge 3) {
        $tickerFromIndex = $columns[2].Trim()
        $statusFromIndex = ''

        if ($section -eq 'tracked' -and $columns.Count -ge 10) {
          $statusFromIndex = Normalize-PickStatus $columns[9].Trim()
        } elseif ($section -eq 'completed') {
          $statusFromIndex = 'completed'
        } elseif ($section -eq 'closed') {
          $statusFromIndex = 'closed'
        }

        if (-not [string]::IsNullOrWhiteSpace($tickerFromIndex) -and -not [string]::IsNullOrWhiteSpace($statusFromIndex)) {
          $indexStatusByTicker[$tickerFromIndex] = $statusFromIndex
        }
      }
    }
  }
}

foreach ($pick in Get-ChildItem -Path $pickDir -Filter '20*.md') {
  $fm = Read-FrontMatter -Path $pick.FullName
  $ticker = $fm['ticker']
  if ([string]::IsNullOrWhiteSpace($ticker)) {
    Write-Output ("SKIP {0} - not an individual pick file" -f $pick.Name)
    continue
  }

  $name = $fm['name']
  $status = Normalize-PickStatus $fm['status']

  if ($indexStatusByTicker.ContainsKey($ticker) -and $indexStatusByTicker[$ticker] -ne $status) {
    Add-Issue -Level 'ERROR' -Area 'Pick data quality' -Message ("Pick status mismatch between INDEX and frontmatter: {0} index={1} file={2}" -f $ticker, $indexStatusByTicker[$ticker], $status)
    Write-Output ("FAIL {0} {1} - status mismatch INDEX={2}, file={3}" -f $ticker, $name, $indexStatusByTicker[$ticker], $status)
    continue
  }

  $current = 0
  [void][int]::TryParse(($fm['current_price_at_pick'] -as [string]), [ref]$current)

  if ($status -eq 'active' -and $current -le 0) {
    Add-Issue -Level 'ERROR' -Area 'Pick data quality' -Message ("Active pick has no usable current_price_at_pick: {0} {1}" -f $ticker, $name)
    Write-Output ("FAIL {0} {1} - current_price_at_pick is missing or zero" -f $ticker, $name)
    continue
  }

  $entryLow = 0
  $entryHigh = 0
  [void][int]::TryParse(($fm['entry_price_low'] -as [string]), [ref]$entryLow)
  [void][int]::TryParse(($fm['entry_price_high'] -as [string]), [ref]$entryHigh)

  if ($status -eq 'active' -and ($entryLow -le 0 -or $entryHigh -le 0)) {
    Add-Issue -Level 'ERROR' -Area 'Pick data quality' -Message ("Active pick has incomplete entry range: {0} {1}" -f $ticker, $name)
    Write-Output ("FAIL {0} {1} - entry range is incomplete" -f $ticker, $name)
    continue
  }

  if ($entryLow -gt 0 -and $entryHigh -gt 0 -and $entryLow -gt $entryHigh) {
    Add-Issue -Level 'ERROR' -Area 'Pick data quality' -Message ("Entry range low is higher than high: {0} {1}" -f $ticker, $name)
    Write-Output ("FAIL {0} {1} - entry range is inverted" -f $ticker, $name)
    continue
  }

  $target1 = 0
  $target2 = 0
  $stopLoss = 0
  [void][int]::TryParse(($fm['target_1'] -as [string]), [ref]$target1)
  [void][int]::TryParse(($fm['target_2'] -as [string]), [ref]$target2)
  [void][int]::TryParse(($fm['stop_loss'] -as [string]), [ref]$stopLoss)

  if ($status -eq 'active' -and ($target1 -le 0 -or $target2 -le 0 -or $stopLoss -le 0)) {
    Add-Issue -Level 'ERROR' -Area 'Pick data quality' -Message ("Active pick has incomplete target/stop metadata: {0} {1}" -f $ticker, $name)
    Write-Output ("FAIL {0} {1} - target or stop-loss metadata is incomplete" -f $ticker, $name)
    continue
  }

  Write-Output ("OK   {0} {1}" -f $ticker, $name)
}

Write-Output ''
Write-Output '== Directory checks =='
foreach ($relative in @('picks/cache', 'picks/alerts')) {
  $path = Join-Path $root $relative
  if (Test-Path $path) {
    Write-Output ("OK   {0}" -f $relative)
  } else {
    Add-Issue -Level 'ERROR' -Area 'Directory checks' -Message ("Missing required directory: {0}" -f $relative)
    Write-Output ("FAIL {0} - missing" -f $relative)
  }
}

Write-Output ''
Write-Output '== MCP config =='
$mcpFile = Join-Path $root '.mcp.json'
if (Test-Path $mcpFile) {
  $mcpText = Get-Content -Path $mcpFile -Raw -Encoding UTF8
  if ($mcpText -match '"playmcp"' -and $mcpText -match 'https://playmcp.kakao.com/mcp') {
    Write-Output 'OK   .mcp.json playmcp'
  } else {
    Add-Issue -Level 'ERROR' -Area 'MCP config' -Message '.mcp.json exists but playmcp configuration is incomplete'
    Write-Output 'FAIL .mcp.json - playmcp configuration is incomplete'
  }
} else {
  Add-Issue -Level 'ERROR' -Area 'MCP config' -Message 'Missing .mcp.json project MCP configuration'
  Write-Output 'FAIL .mcp.json - missing'
}

Write-Output ''
Write-Output '== Flow/Momentum tracking =='
$flowAgent = Join-Path $root '.claude/agents/flow-momentum-tracker.md'
$flowPicks = Join-Path $root 'picks/2026-05-12_flow_momentum_picks.md'
$flowReport = Join-Path $root 'picks/tracking_weekly_cumulative_flow_momentum.md'

foreach ($required in @($flowAgent, $flowPicks, $flowReport)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Flow/Momentum tracking' -Message ("Missing required tracking file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if ((Test-Path $flowReport) -and (Test-Path $flowPicks)) {
  $reportText = Get-Content -Path $flowReport -Raw -Encoding UTF8
  $pickText = Get-Content -Path $flowPicks -Raw -Encoding UTF8
  foreach ($ticker in @('000660', '005930', '018260')) {
    if ($reportText -notmatch $ticker -or $pickText -notmatch $ticker) {
      Add-Issue -Level 'ERROR' -Area 'Flow/Momentum tracking' -Message ("Tracking files missing ticker: {0}" -f $ticker)
      Write-Output ("FAIL ticker {0} - missing from tracking files" -f $ticker)
    }
  }
  foreach ($requiredText in @('Active Tracking', 'Excluded Stop-Loss', 'Week 0')) {
    if ($reportText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Flow/Momentum tracking' -Message ("Tracking report missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL tracking report - missing {0}" -f $requiredText)
    }
  }
}

Write-Output ''
Write-Output '== Entry/Exit timing =='
$timingAgent = Join-Path $root '.claude/agents/entry-exit-timing-strategist.md'
$timingPlaybook = Join-Path $root 'picks/entry_exit_timing_playbook.md'
$pullbackAgent = Join-Path $root '.claude/agents/pullback-analyst.md'
$pullbackPy = Join-Path $root 'scripts/run_pullback_screen.py'
$pullbackPs1 = Join-Path $root 'scripts/run_pullback_screen.ps1'
$pullbackDocs = Join-Path $root 'docs/pullback_screen.md'
$pullbackCandidates = Join-Path $root 'picks/cache/pullback_candidates.json'

foreach ($required in @($timingAgent, $timingPlaybook, $pullbackAgent, $pullbackPy, $pullbackPs1, $pullbackDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Entry/Exit timing' -Message ("Missing required timing file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $timingPlaybook) {
  $timingText = Get-Content -Path $timingPlaybook -Raw -Encoding UTF8
  foreach ($requiredText in @('entry-exit-timing-strategist', 'No direct trading instruction', 'entry_zone', 'exit_plan', 'Kelly-style sizing')) {
    if ($timingText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Entry/Exit timing' -Message ("Timing playbook missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL timing playbook - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $pullbackAgent) {
  $pullbackAgentText = Get-Content -Path $pullbackAgent -Raw -Encoding UTF8
  foreach ($requiredText in @('pullback-analyst', 'Signal 4', '1.5:1')) {
    if ($pullbackAgentText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Entry/Exit timing' -Message ("Pullback agent missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL pullback agent - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $pullbackDocs) {
  $pullbackDocsText = Get-Content -Path $pullbackDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('pullback_candidates.json', '4-signal', 'ENTRY')) {
    if ($pullbackDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Entry/Exit timing' -Message ("Pullback docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL pullback docs - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $pullbackCandidates) {
  try {
    $pullbackJson = Get-Content -Path $pullbackCandidates -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $pullbackJson.candidates) {
      Add-Issue -Level 'ERROR' -Area 'Entry/Exit timing' -Message 'pullback_candidates.json missing candidates'
      Write-Output 'FAIL pullback candidates - missing candidates'
    } else {
      Write-Output 'OK   .\picks\cache\pullback_candidates.json'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'Entry/Exit timing' -Message ("Could not parse pullback candidates: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL pullback candidates - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'Entry/Exit timing' -Message 'Missing pullback candidates snapshot: picks/cache/pullback_candidates.json'
  Write-Output 'WARN pullback candidates - missing'
}

Write-Output ''
Write-Output '== US close Korea preopen strategy =='
$usCloseAgent = Join-Path $root '.claude/agents/us-close-korea-strategist.md'
$watchlistFile = Join-Path $root 'picks/WATCHLIST.md'
$usClosePy = Join-Path $root 'scripts/collect_us_close_data.py'
$usClosePs1 = Join-Path $root 'scripts/collect_us_close_data.ps1'
$preopenFilterPy = Join-Path $root 'scripts/run_preopen_filter.py'
$preopenFilterPs1 = Join-Path $root 'scripts/run_preopen_filter.ps1'
$usCloseDocs = Join-Path $root 'docs/us_close_korea_preopen.md'
$usCloseSnapshot = Join-Path $root 'picks/cache/us_close_snapshot.json'
$preopenCandidates = Join-Path $root 'picks/cache/preopen_candidates.json'
$preopenFilteredCandidates = Join-Path $root 'picks/cache/preopen_filtered_candidates.json'

foreach ($required in @($usCloseAgent, $watchlistFile, $usClosePy, $usClosePs1, $preopenFilterPy, $preopenFilterPs1, $usCloseDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("Missing required preopen strategy file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $usCloseAgent) {
  $usCloseText = Get-Content -Path $usCloseAgent -Raw -Encoding UTF8
  foreach ($requiredText in @('name: us-close-korea-strategist', 'WATCHLIST.md', 'Hard Block', 'preopen_candidates', 'us-close-korea-strategist')) {
    if ($usCloseText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("Preopen strategy agent missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL preopen agent - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $watchlistFile) {
  $watchlistText = Get-Content -Path $watchlistFile -Raw -Encoding UTF8
  foreach ($requiredText in @('WATCHLIST', 'BLOCK', '2026-')) {
    if ($watchlistText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("WATCHLIST missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL WATCHLIST - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $usCloseDocs) {
  $usCloseDocsText = Get-Content -Path $usCloseDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('us_close_snapshot.json', 'preopen_candidates.json', 'preopen_filtered_candidates.json', 'Capital Protection Gate')) {
    if ($usCloseDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("US close preopen docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL us close docs - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $preopenFilteredCandidates) {
  try {
    $filteredJson = Get-Content -Path $preopenFilteredCandidates -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $filteredJson.final_candidates) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message 'preopen_filtered_candidates.json missing final_candidates'
      Write-Output 'FAIL preopen filtered candidates - missing final_candidates'
    } else {
      Write-Output 'OK   .\picks\cache\preopen_filtered_candidates.json'
    }
    if ($filteredJson.final_candidates.Count -gt 3) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message 'preopen_filtered_candidates.json has more than 3 candidates'
      Write-Output 'FAIL preopen filtered candidates - more than 3 candidates'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("Could not parse preopen filtered candidates: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL preopen filtered candidates - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'US close Korea preopen strategy' -Message 'Missing preopen filtered candidates snapshot: picks/cache/preopen_filtered_candidates.json'
  Write-Output 'WARN preopen filtered candidates - missing'
}

if (Test-Path $preopenCandidates) {
  try {
    $preopenJson = Get-Content -Path $preopenCandidates -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $preopenJson.preopen_candidates) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message 'preopen_candidates.json missing preopen_candidates'
      Write-Output 'FAIL preopen candidates - missing preopen_candidates'
    } else {
      Write-Output 'OK   .\picks\cache\preopen_candidates.json'
    }
    if ($preopenJson.preopen_candidates.Count -gt 3) {
      Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message 'preopen_candidates.json has more than 3 candidates'
      Write-Output 'FAIL preopen candidates - more than 3 candidates'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("Could not parse preopen candidates: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL preopen candidates - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'US close Korea preopen strategy' -Message 'Missing preopen candidates snapshot: picks/cache/preopen_candidates.json'
  Write-Output 'WARN preopen candidates - missing'
}

if (Test-Path $usCloseSnapshot) {
  try {
    $usCloseJson = Get-Content -Path $usCloseSnapshot -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $usCloseJson.quotes -or $usCloseJson.quotes.Count -lt 10) {
      Add-Issue -Level 'WARN' -Area 'US close Korea preopen strategy' -Message 'US close snapshot has too few quotes'
      Write-Output 'WARN US close snapshot - too few quotes'
    } else {
      Write-Output 'OK   .\picks\cache\us_close_snapshot.json'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'US close Korea preopen strategy' -Message ("Could not parse US close snapshot: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL US close snapshot - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'US close Korea preopen strategy' -Message 'Missing US close snapshot: picks/cache/us_close_snapshot.json'
  Write-Output 'WARN US close snapshot - missing'
}

Write-Output ''
Write-Output '== Paper trading =='
$paperSimulator = Join-Path $root 'scripts/paper_trade_simulator.ps1'
$paperRules = Join-Path $root 'picks/paper_trading_rules.json'
$paperPrices = Join-Path $root 'picks/paper_price_snapshot.json'
$paperDocs = Join-Path $root 'docs/paper_trading_options.md'

foreach ($required in @($paperSimulator, $paperRules, $paperPrices, $paperDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Paper trading' -Message ("Missing required paper trading file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $paperRules) {
  $paperRulesText = Get-Content -Path $paperRules -Raw -Encoding UTF8
  foreach ($ticker in @('000660', '005930', '018260')) {
    # Skip closed/completed picks — they are no longer required in paper trading rules
    $indexStatus = $indexStatusByTicker[$ticker]
    if ($indexStatus -eq 'closed' -or $indexStatus -eq 'completed') {
      continue
    }
    if ($paperRulesText -notmatch $ticker) {
      Add-Issue -Level 'ERROR' -Area 'Paper trading' -Message ("Paper trading rules missing ticker: {0}" -f $ticker)
      Write-Output ("FAIL paper rules - missing {0}" -f $ticker)
    }
  }
}

Write-Output ''
Write-Output '== Market data crawler =='
$marketCrawlerPy = Join-Path $root 'scripts/collect_market_data.py'
$marketCrawlerPs1 = Join-Path $root 'scripts/collect_market_data.ps1'
$marketCrawlerDocs = Join-Path $root 'docs/market_data_crawler.md'

foreach ($required in @($marketCrawlerPy, $marketCrawlerPs1, $marketCrawlerDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Market data crawler' -Message ("Missing required market data crawler file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $marketCrawlerDocs) {
  $marketCrawlerDocsText = Get-Content -Path $marketCrawlerDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('JSON', 'TOSS_INVEST_TOKEN', 'market_data_snapshot.json', 'technical', 'AllowPartialWrite', 'UpdatePaperPriceSnapshot')) {
    if ($marketCrawlerDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Market data crawler' -Message ("Market data crawler docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL market data crawler docs - missing {0}" -f $requiredText)
    }
  }
}

Write-Output ''
Write-Output '== Flow data collector =='
$flowCollectorPy = Join-Path $root 'scripts/collect_flow_data.py'
$flowCollectorPs1 = Join-Path $root 'scripts/collect_flow_data.ps1'
$flowCollectorDocs = Join-Path $root 'docs/flow_data_collector.md'
$flowSnapshot = Join-Path $root 'picks/cache/flow_snapshot.json'

foreach ($required in @($flowCollectorPy, $flowCollectorPs1, $flowCollectorDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Flow data collector' -Message ("Missing required flow data collector file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $flowCollectorDocs) {
  $flowCollectorDocsText = Get-Content -Path $flowCollectorDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('flow_snapshot.json', 'foreign_net_buy_5d', 'institution_net_buy_5d')) {
    if ($flowCollectorDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Flow data collector' -Message ("Flow data collector docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL flow data collector docs - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $flowSnapshot) {
  try {
    $flowJson = Get-Content -Path $flowSnapshot -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $flowJson.items) {
      Add-Issue -Level 'ERROR' -Area 'Flow data collector' -Message 'flow_snapshot.json missing items'
      Write-Output 'FAIL flow snapshot - missing items'
    } else {
      Write-Output 'OK   .\picks\cache\flow_snapshot.json'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'Flow data collector' -Message ("Could not parse flow snapshot: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL flow snapshot - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'Flow data collector' -Message 'Missing operating flow snapshot: picks/cache/flow_snapshot.json'
  Write-Output 'WARN flow snapshot - missing'
}

Write-Output ''
Write-Output '== Fundamentals collector =='
$fundamentalsPy = Join-Path $root 'scripts/collect_fundamentals.py'
$fundamentalsPs1 = Join-Path $root 'scripts/collect_fundamentals.ps1'
$fundamentalsDocs = Join-Path $root 'docs/fundamentals_collector.md'
$fundamentalsSnapshot = Join-Path $root 'picks/cache/fundamentals_snapshot.json'

foreach ($required in @($fundamentalsPy, $fundamentalsPs1, $fundamentalsDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Fundamentals collector' -Message ("Missing required fundamentals collector file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $fundamentalsDocs) {
  $fundamentalsDocsText = Get-Content -Path $fundamentalsDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('OpenDART', 'OPENDART_API_KEY', 'Provider', 'pykrx', 'BPS', 'PER', 'PBR', 'fundamentals_snapshot.json')) {
    if ($fundamentalsDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Fundamentals collector' -Message ("Fundamentals collector docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL fundamentals collector docs - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $fundamentalsSnapshot) {
  try {
    $fundamentalsJson = Get-Content -Path $fundamentalsSnapshot -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($fundamentalsJson.mode -ne 'live') {
      Add-Issue -Level 'ERROR' -Area 'Fundamentals collector' -Message 'fundamentals_snapshot.json is not a live snapshot'
      Write-Output 'FAIL fundamentals snapshot - mode is not live'
    } else {
      Write-Output 'OK   .\picks\cache\fundamentals_snapshot.json live'
    }

    if ($fundamentalsJson.provider -ne 'opendart' -and $fundamentalsJson.provider -ne 'pykrx') {
      Add-Issue -Level 'ERROR' -Area 'Fundamentals collector' -Message ("Unsupported fundamentals provider in snapshot: {0}" -f $fundamentalsJson.provider)
      Write-Output ("FAIL fundamentals snapshot - unsupported provider {0}" -f $fundamentalsJson.provider)
    }

    $badItems = @($fundamentalsJson.items | Where-Object { -not $_.ok })
    if ($badItems.Count -gt 0) {
      Add-Issue -Level 'ERROR' -Area 'Fundamentals collector' -Message ("Fundamentals snapshot has failed items: {0}" -f (($badItems | ForEach-Object ticker) -join ', '))
      Write-Output ("FAIL fundamentals snapshot - failed items {0}" -f (($badItems | ForEach-Object ticker) -join ', '))
    }

    if ($fundamentalsJson.provider -eq 'opendart') {
      $missingGateMetrics = @($fundamentalsJson.items | Where-Object {
        $null -eq $_.gate_metrics -or
        ($null -eq $_.gate_metrics.roe -and $null -eq $_.gate_metrics.debt_ratio -and $null -eq $_.gate_metrics.current_ratio)
      })
      if ($missingGateMetrics.Count -gt 0) {
        Add-Issue -Level 'WARN' -Area 'Fundamentals collector' -Message ("OpenDART snapshot has items without gate metrics: {0}" -f (($missingGateMetrics | ForEach-Object ticker) -join ', '))
        Write-Output ("WARN fundamentals snapshot - missing gate metrics {0}" -f (($missingGateMetrics | ForEach-Object ticker) -join ', '))
      } else {
        Write-Output 'OK   OpenDART gate metrics'
      }
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'Fundamentals collector' -Message ("Could not parse fundamentals snapshot: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL fundamentals snapshot - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'Fundamentals collector' -Message 'Missing operating fundamentals snapshot: picks/cache/fundamentals_snapshot.json'
  Write-Output 'WARN fundamentals snapshot - missing'
}

Write-Output ''
Write-Output '== Candidate board =='
$candidateBoardPy = Join-Path $root 'scripts/run_candidate_board.py'
$candidateBoardPs1 = Join-Path $root 'scripts/run_candidate_board.ps1'
$candidateBoardDocs = Join-Path $root 'docs/candidate_board.md'
$candidateBoardSnapshot = Join-Path $root 'picks/cache/candidate_board.json'

foreach ($required in @($candidateBoardPy, $candidateBoardPs1, $candidateBoardDocs)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Candidate board' -Message ("Missing required candidate board file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $candidateBoardDocs) {
  $candidateBoardDocsText = Get-Content -Path $candidateBoardDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('candidate_board.json', 'preopen', 'pullback', 'fundamentals')) {
    if ($candidateBoardDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Candidate board' -Message ("Candidate board docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL candidate board docs - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $candidateBoardSnapshot) {
  try {
    $candidateBoardJson = Get-Content -Path $candidateBoardSnapshot -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $candidateBoardJson.rows) {
      Add-Issue -Level 'ERROR' -Area 'Candidate board' -Message 'candidate_board.json missing rows'
      Write-Output 'FAIL candidate board - missing rows'
    } else {
      Write-Output 'OK   .\picks\cache\candidate_board.json'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'Candidate board' -Message ("Could not parse candidate board: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL candidate board - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'Candidate board' -Message 'Missing operating candidate board: picks/cache/candidate_board.json'
  Write-Output 'WARN candidate board - missing'
}

Write-Output ''
Write-Output '== Fiscal.ai integration =='
$fiscalAiDocs = Join-Path $root 'docs/fiscal_ai_integration.md'
$fiscalAiCheckPy = Join-Path $root 'scripts/check_fiscal_ai.py'
$fiscalAiCheckPs1 = Join-Path $root 'scripts/check_fiscal_ai.ps1'
$fiscalAiCollectorPy = Join-Path $root 'scripts/collect_fiscal_ai.py'
$fiscalAiCollectorPs1 = Join-Path $root 'scripts/collect_fiscal_ai.ps1'
$fiscalAiSnapshot = Join-Path $root 'picks/cache/fiscal_ai_snapshot.json'

foreach ($required in @($fiscalAiCheckPy, $fiscalAiCheckPs1, $fiscalAiCollectorPy, $fiscalAiCollectorPs1)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Fiscal.ai integration' -Message ("Missing required Fiscal.ai check file: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

if (Test-Path $fiscalAiDocs) {
  Write-Output ("OK   {0}" -f (Resolve-Path -Path $fiscalAiDocs -Relative))
  $fiscalAiDocsText = Get-Content -Path $fiscalAiDocs -Raw -Encoding UTF8
  foreach ($requiredText in @('Fiscal.ai', 'FISCAL_AI_API_KEY', 'https://api.fiscal.ai/mcp', 'candidate_board.json')) {
    if ($fiscalAiDocsText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Fiscal.ai integration' -Message ("Fiscal.ai docs missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL fiscal.ai docs - missing {0}" -f $requiredText)
    }
  }
} else {
  Add-Issue -Level 'ERROR' -Area 'Fiscal.ai integration' -Message 'Missing docs/fiscal_ai_integration.md'
  Write-Output 'FAIL docs/fiscal_ai_integration.md - missing'
}

if (Test-Path $fiscalAiSnapshot) {
  try {
    $fiscalAiJson = Get-Content -Path $fiscalAiSnapshot -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -eq $fiscalAiJson.items) {
      Add-Issue -Level 'ERROR' -Area 'Fiscal.ai integration' -Message 'fiscal_ai_snapshot.json missing items'
      Write-Output 'FAIL fiscal.ai snapshot - missing items'
    } else {
      Write-Output 'OK   .\picks\cache\fiscal_ai_snapshot.json'
    }
  } catch {
    Add-Issue -Level 'ERROR' -Area 'Fiscal.ai integration' -Message ("Could not parse Fiscal.ai snapshot: {0}" -f $_.Exception.Message)
    Write-Output 'FAIL fiscal.ai snapshot - invalid JSON'
  }
} else {
  Add-Issue -Level 'WARN' -Area 'Fiscal.ai integration' -Message 'Missing Fiscal.ai snapshot: picks/cache/fiscal_ai_snapshot.json'
  Write-Output 'WARN fiscal.ai snapshot - missing'
}

Write-Output ''
Write-Output '== Capital protection gate =='
$policyFile = Join-Path $root 'INVESTMENT_POLICY.md'
$checklistFile = Join-Path $root 'docs/pre_trade_checklist.md'
$currentStateFile = Join-Path $root 'CURRENT_STATE.md'
$postmortemDir = Join-Path $root 'picks/postmortems'
$capitalAgents = @(
  '.claude/agents/market-regime-analyst.md',
  '.claude/agents/portfolio-manager.md',
  '.claude/agents/position-sizing-analyst.md',
  '.claude/agents/performance-reviewer.md'
)

foreach ($required in @($policyFile, $checklistFile, $currentStateFile, $postmortemDir)) {
  if (Test-Path $required) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $required -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Capital protection gate' -Message ("Missing required risk-control file or directory: {0}" -f $required)
    Write-Output ("FAIL {0} - missing" -f $required)
  }
}

foreach ($relative in $capitalAgents) {
  $path = Join-Path $root $relative
  if (Test-Path $path) {
    Write-Output ("OK   {0}" -f (Resolve-Path -Path $path -Relative))
  } else {
    Add-Issue -Level 'ERROR' -Area 'Capital protection gate' -Message ("Missing required risk-control agent: {0}" -f $relative)
    Write-Output ("FAIL {0} - missing" -f $relative)
  }
}

if (Test-Path $currentStateFile) {
  $currentStateText = Get-Content -Path $currentStateFile -Raw -Encoding UTF8
  foreach ($requiredText in @('Canonical Files', 'Archived Files', 'Pick Status Rules', 'Validation Commands')) {
    if ($currentStateText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Capital protection gate' -Message ("Current state file missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL current state - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $policyFile) {
  $policyText = Get-Content -Path $policyFile -Raw -Encoding UTF8
  foreach ($requiredText in @('risk_single_position_max', 'risk_stop_loss_budget', 'risk_sector_exposure_max', 'new_pick_approval_gate')) {
    if ($policyText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Capital protection gate' -Message ("Investment policy missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL investment policy - missing {0}" -f $requiredText)
    }
  }
}

if (Test-Path $checklistFile) {
  $checklistText = Get-Content -Path $checklistFile -Raw -Encoding UTF8
  foreach ($requiredText in @('Hard Block', 'Quality Gate', 'Position Gate', 'Pre-Trade Gate')) {
    if ($checklistText -notmatch [regex]::Escape($requiredText)) {
      Add-Issue -Level 'ERROR' -Area 'Capital protection gate' -Message ("Pre-trade checklist missing required text: {0}" -f $requiredText)
      Write-Output ("FAIL pre-trade checklist - missing {0}" -f $requiredText)
    }
  }
}

foreach ($relative in $capitalAgents) {
  $path = Join-Path $root $relative
  if (Test-Path $path) {
    $agentText = Get-Content -Path $path -Raw -Encoding UTF8
    if ($agentText -notmatch '```json') {
      Add-Issue -Level 'ERROR' -Area 'Capital protection gate' -Message ("Risk-control agent missing JSON contract: {0}" -f $relative)
      Write-Output ("FAIL {0} - missing JSON contract" -f $relative)
    }
  }
}

Write-Output ''
Write-Output '== Summary =='
$errors = @($issues | Where-Object Level -eq 'ERROR')
$warnings = @($issues | Where-Object Level -eq 'WARN')
Write-Output ("Errors: {0}, Warnings: {1}" -f $errors.Count, $warnings.Count)

foreach ($issue in $issues) {
  Write-Output ("{0} [{1}] {2}" -f $issue.Level, $issue.Area, $issue.Message)
}

if ($errors.Count -gt 0 -and -not $WarnOnly) {
  exit 1
}
