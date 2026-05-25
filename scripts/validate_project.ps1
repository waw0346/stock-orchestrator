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
    'market-regime-analyst',
    'portfolio-manager',
    'position-sizing-analyst',
    'performance-reviewer'
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

foreach ($required in @($timingAgent, $timingPlaybook)) {
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
    if ($paperRulesText -notmatch $ticker) {
      Add-Issue -Level 'ERROR' -Area 'Paper trading' -Message ("Paper trading rules missing ticker: {0}" -f $ticker)
      Write-Output ("FAIL paper rules - missing {0}" -f $ticker)
    }
  }
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
