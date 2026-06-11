param(
  [string]$SourcePortfolioPath = 'picks/2026-05-12_flow_momentum_picks.md',
  [string]$TrackingPath = 'picks/tracking_weekly_cumulative_flow_momentum.md',
  [string]$PlaybookPath = 'picks/entry_exit_timing_playbook.md',
  [string]$DataPath,
  [datetime]$Now = (Get-Date),
  [switch]$NoPrompt,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not [Environment]::UserInteractive) {
  Write-Host "[INFO] Non-interactive environment detected. Enforcing -NoPrompt." -ForegroundColor Gray
  $NoPrompt = $true
}

function Resolve-WorkspacePath {
  param([string]$Path)
  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $null
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $Path
  }
  return Join-Path (Get-Location) $Path
}

function Format-Won {
  param([long]$Value)
  return ('{0:N0}원' -f $Value)
}

function Format-Pct {
  param([double]$Value)
  $sign = if ($Value -gt 0) { '+' } elseif ($Value -lt 0) { '' } else { '' }
  return ('{0}{1:N1}%' -f $sign, $Value)
}

function Get-LatestCompletedWeekCloseDate {
  param([datetime]$NowLocal)

  $today = $NowLocal.Date
  $day = [int]$today.DayOfWeek

  $sub = switch ($day) {
    0 { 2 } # Sunday
    1 { 3 } # Monday
    2 { 4 } # Tuesday
    3 { 5 } # Wednesday
    4 { 6 } # Thursday
    5 {     # Friday
      $krxClose = Get-Date -Year $today.Year -Month $today.Month -Day $today.Day -Hour 15 -Minute 30 -Second 0
      if ($NowLocal -lt $krxClose) { 7 } else { 0 }
    }
    6 { 1 } # Saturday
  }

  return $today.AddDays(-$sub)
}

function Parse-NumberFromWon {
  param([string]$Text)
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $null
  }
  $digits = ($Text -replace '[^0-9]', '')
  if ([string]::IsNullOrWhiteSpace($digits)) {
    return $null
  }
  return [long]$digits
}

function Get-FlowMomentumPickTable {
  param([string]$Markdown)

  $lines = $Markdown -split "`r?`n"
  $tableStart = ($lines | Select-String -SimpleMatch '| SK하이닉스' | Select-Object -First 1).LineNumber
  if (-not $tableStart) {
    throw "Failed to find pick summary table in source portfolio."
  }

  $rows = @()
  for ($i = $tableStart - 1; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line -notmatch '^\|') {
      break
    }
    if ($line -match '^\|\s*[-: ]+\|') {
      continue
    }
    $cols = $line -split '\|'
    if ($cols.Count -lt 7) {
      continue
    }
    $name = $cols[1].Trim()
    $code = $cols[2].Trim()
    if ($code -notmatch '^\d{6}$') {
      continue
    }
    $base = Parse-NumberFromWon $cols[3]
    $target = Parse-NumberFromWon $cols[4]
    $stop = Parse-NumberFromWon $cols[5]
    $rows += [pscustomobject]@{ ticker = $code; name = $name; base = $base; target = $target; stop = $stop }
  }
  return $rows
}

function Get-ActiveTrackingTickers {
  param([string]$TrackingMarkdown)

  $lines = $TrackingMarkdown -split "`r?`n"
  $start = ($lines | Select-String -SimpleMatch '## Active Tracking' | Select-Object -First 1).LineNumber
  if (-not $start) {
    throw "Failed to locate '## Active Tracking' section."
  }

  $tickers = New-Object System.Collections.Generic.List[string]
  for ($i = $start; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line -match '^##\s+') {
      break
    }
    if ($line -notmatch '^\|') {
      continue
    }
    if ($line -match '^\|\s*[-: ]+\|') {
      continue
    }
    $cols = $line -split '\|'
    if ($cols.Count -lt 4) {
      continue
    }
    $ticker = $cols[2].Trim()
    $status = if ($cols.Count -ge 10) { $cols[9].Trim() } else { '' }
    if ($ticker -match '^\d{6}$' -and $status -eq 'active') {
      $tickers.Add($ticker) | Out-Null
    }
  }
  return @($tickers)
}

function Read-WeeklyData {
  param(
    [string[]]$Tickers,
    [hashtable]$PickByTicker,
    [datetime]$WeekCloseDate,
    [string]$DataPathValue,
    [switch]$NoPromptValue
  )

  if (-not [string]::IsNullOrWhiteSpace($DataPathValue)) {
    $resolved = Resolve-WorkspacePath $DataPathValue
    if (-not (Test-Path $resolved)) {
      throw "Missing -DataPath JSON file: $resolved"
    }
    $json = Get-Content -Path $resolved -Raw -Encoding UTF8 | ConvertFrom-Json
    $data = @{}
    foreach ($ticker in $Tickers) {
      $stock = $json.stocks.$ticker
      if ($null -eq $stock) {
        throw "DataPath missing required ticker '$ticker' under stocks."
      }
      $data[$ticker] = [pscustomobject]@{
        close = [long]$stock.close
        foreign_net_shares = [long]$stock.foreign_net_shares
        inst_net_shares = [long]$stock.inst_net_shares
        rsi14 = [double]$stock.rsi14
        week52_high = if ($null -ne $stock.week52_high) { [long]$stock.week52_high } else { $null }
        sources = if ($null -ne $stock.sources) { [string]$stock.sources } else { '' }
      }
    }
    return $data
  }

  if ($NoPromptValue) {
    throw "No weekly data provided. Pass -DataPath <json> or run without -NoPrompt for interactive entry."
  }

  Write-Output ''
  Write-Output '== Weekly data input (interactive) =='
  Write-Output ("Week close date (KRX): {0}" -f $WeekCloseDate.ToString('yyyy-MM-dd'))
  Write-Output 'Enter integers only. Leave blank to abort.'

  $result = @{}
  foreach ($ticker in $Tickers) {
    $pick = $PickByTicker[$ticker]
    Write-Output ''
    Write-Output ("[{0}] {1}" -f $ticker, $pick.name)
    $closeText = Read-Host "weekly close (won) e.g. 1941000"
    if ([string]::IsNullOrWhiteSpace($closeText)) { throw 'Aborted by user (missing close).' }
    $foreignText = Read-Host "foreign net shares (week sum) e.g. -2969723"
    if ([string]::IsNullOrWhiteSpace($foreignText)) { throw 'Aborted by user (missing foreign).' }
    $instText = Read-Host "institution net shares (week sum) e.g. 1276913"
    if ([string]::IsNullOrWhiteSpace($instText)) { throw 'Aborted by user (missing institution).' }
    $rsiText = Read-Host "RSI(14) e.g. 65.4"
    if ([string]::IsNullOrWhiteSpace($rsiText)) { throw 'Aborted by user (missing RSI).' }
    $highText = Read-Host "52w high (optional, won) e.g. 1995000"

    $result[$ticker] = [pscustomobject]@{
      close = [long]$closeText
      foreign_net_shares = [long]$foreignText
      inst_net_shares = [long]$instText
      rsi14 = [double]$rsiText
      week52_high = if ([string]::IsNullOrWhiteSpace($highText)) { $null } else { [long]$highText }
      sources = ''
    }
  }

  return $result
}

function Compute-Returns {
  param(
    [long]$Base,
    [long]$Target,
    [long]$Stop,
    [long]$Close
  )

  $cum = (($Close - $Base) / [double]$Base) * 100.0
  $targetRate = (($Close - $Base) / [double]($Target - $Base)) * 100.0
  $isStop = $Close -le $Stop
  $isTarget = $Close -ge $Target

  return [pscustomobject]@{
    cumulative_return_pct = $cum
    target_achievement_pct = $targetRate
    stop_triggered = $isStop
    target_hit = $isTarget
  }
}

function Update-ActiveTrackingTable {
  param(
    [string]$TrackingMarkdown,
    [hashtable]$PickByTicker,
    [hashtable]$WeeklyByTicker,
    [string]$ReviewDate
  )

  $lines = $TrackingMarkdown -split "`r?`n"
  $start = ($lines | Select-String -SimpleMatch '## Active Tracking' | Select-Object -First 1).LineNumber
  if (-not $start) {
    throw "Failed to locate '## Active Tracking'."
  }

  for ($i = $start; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^##\s+' -and $i -ne ($start - 1)) {
      break
    }
    if ($lines[$i] -notmatch '^\|') {
      continue
    }
    if ($lines[$i] -match '^\|\s*[-: ]+\|') {
      continue
    }
    $cols = $lines[$i] -split '\|'
    if ($cols.Count -lt 11) {
      continue
    }

    $ticker = $cols[2].Trim()
    $status = $cols[9].Trim()
    if ($status -ne 'active') {
      continue
    }
    if (-not $WeeklyByTicker.ContainsKey($ticker)) {
      continue
    }

    $pick = $PickByTicker[$ticker]
    $weekly = $WeeklyByTicker[$ticker]
    $metrics = Compute-Returns -Base $pick.base -Target $pick.target -Stop $pick.stop -Close $weekly.close

    # Columns: | 종목 | 코드 | 기준가 | 현재가 | 목표가 | 손절가 | 누적수익률 | 목표달성률 | 상태 | 최근점검 |
    $cols[4] = ' ' + (Format-Won $weekly.close) + ' '
    $cols[7] = ' ' + (Format-Pct $metrics.cumulative_return_pct) + ' '
    $cols[8] = ' ' + ('{0:N1}%' -f $metrics.target_achievement_pct) + ' '
    $cols[10] = ' ' + $ReviewDate + ' '

    $lines[$i] = ($cols -join '|')
  }

  return ($lines -join "`r`n")
}

function Move-StopLossExclusions {
  param(
    [string]$TrackingMarkdown,
    [hashtable]$PickByTicker,
    [hashtable]$WeeklyByTicker,
    [string]$ExcludeDate
  )

  $excluded = @()
  foreach ($ticker in @($WeeklyByTicker.Keys)) {
    $pick = $PickByTicker[$ticker]
    $weekly = $WeeklyByTicker[$ticker]
    if ($weekly.close -le $pick.stop) {
      $excluded += $ticker
    }
  }

  if ($excluded.Count -eq 0) {
    return [pscustomobject]@{ markdown = $TrackingMarkdown; excluded = @() }
  }

  $lines = $TrackingMarkdown -split "`r?`n"

  # Remove from Active Tracking (row-level).
  $activeStart = ($lines | Select-String -SimpleMatch '## Active Tracking' | Select-Object -First 1).LineNumber
  if (-not $activeStart) {
    throw "Failed to locate '## Active Tracking'."
  }
  for ($i = $activeStart; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^##\s+' -and $i -ne ($activeStart - 1)) {
      break
    }
    if ($lines[$i] -notmatch '^\|') {
      continue
    }
    $cols = $lines[$i] -split '\|'
    if ($cols.Count -lt 11) {
      continue
    }
    $ticker = $cols[2].Trim()
    if ($excluded -contains $ticker) {
      $lines[$i] = $null
    }
  }
  $lines = @($lines | Where-Object { $null -ne $_ })

  # Append to Excluded Stop-Loss table (right after header row).
  $exStart = ($lines | Select-String -SimpleMatch '## Excluded Stop-Loss' | Select-Object -First 1).LineNumber
  if (-not $exStart) {
    throw "Failed to locate '## Excluded Stop-Loss'."
  }
  $insertAt = $null
  for ($i = $exStart; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\|\s*-+\s*\|') {
      $insertAt = $i + 1
      break
    }
  }
  if ($null -eq $insertAt) {
    throw "Failed to find Excluded Stop-Loss table separator row."
  }

  $newRows = @()
  foreach ($ticker in $excluded) {
    $pick = $PickByTicker[$ticker]
    $weekly = $WeeklyByTicker[$ticker]
    $retPct = (($weekly.close - $pick.base) / [double]$pick.base) * 100.0
    $newRows += ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f
      $ExcludeDate,
      $pick.name,
      $ticker,
      (Format-Won $weekly.close),
      (Format-Pct $retPct),
      'weekly_close_at_or_below_stop_loss'
    )
  }

  $lines = @(
    $lines[0..($insertAt-1)]
    $newRows
    $lines[$insertAt..($lines.Count-1)]
  )

  return [pscustomobject]@{ markdown = ($lines -join "`r`n"); excluded = $excluded }
}

function Append-WeeklySection {
  param(
    [string]$TrackingMarkdown,
    [datetime]$WeekCloseDate,
    [hashtable]$PickByTicker,
    [hashtable]$WeeklyByTicker,
    [string[]]$ExcludedTickers = @(),
    [string]$MarketState = '시장 상태:'
  )

  $weekStr = $WeekCloseDate.ToString('yyyy-MM-dd')
  $weekNumbers = @()
  foreach ($m in [regex]::Matches($TrackingMarkdown, '^## Week\s+(\d+):', [System.Text.RegularExpressions.RegexOptions]::Multiline)) {
    $weekNumbers += [int]$m.Groups[1].Value
  }
  $nextWeek = if ($weekNumbers.Count -eq 0) { 0 } else { ($weekNumbers | Measure-Object -Maximum).Maximum + 1 }

  $rows = @()
  foreach ($ticker in ($WeeklyByTicker.Keys | Sort-Object)) {
    $pick = $PickByTicker[$ticker]
    $weekly = $WeeklyByTicker[$ticker]
    $metrics = Compute-Returns -Base $pick.base -Target $pick.target -Stop $pick.stop -Close $weekly.close
    $flow = ("외인 {0}{1:N0}주 / 기관 {2}{3:N0}주" -f
      $(if ($weekly.foreign_net_shares -ge 0) { '+' } else { '' }),
      $weekly.foreign_net_shares,
      $(if ($weekly.inst_net_shares -ge 0) { '+' } else { '' }),
      $weekly.inst_net_shares
    )
    $mom = if ($weekly.week52_high) {
      $pct = ($weekly.close / [double]$weekly.week52_high) * 100.0
      ("RSI(14) {0:N1}, 52주 고점({1}) 대비 {2:N1}%" -f $weekly.rsi14, (Format-Won $weekly.week52_high), $pct)
    } else {
      ("RSI(14) {0:N1}, 52주 고점 대비: 확인 필요" -f $weekly.rsi14)
    }
    $judgement = if ($metrics.stop_triggered) { 'Excluded Stop-Loss' } elseif ($metrics.target_hit) { 'Target Hit' } else { 'Hold' }
    $rows += ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} |" -f
      $pick.name,
      (Format-Won $weekly.close),
      (Format-Pct $metrics.cumulative_return_pct),
      ('{0:N1}%' -f $metrics.target_achievement_pct),
      $flow,
      $mom,
      $judgement
    )
  }

  $excludedBlock = ''
  if ($ExcludedTickers.Count -gt 0) {
    $exRows = @()
    foreach ($ticker in $ExcludedTickers) {
      if (-not $PickByTicker.ContainsKey($ticker) -or -not $WeeklyByTicker.ContainsKey($ticker)) {
        continue
      }
      $pick = $PickByTicker[$ticker]
      $weekly = $WeeklyByTicker[$ticker]
      $retPct = (($weekly.close - $pick.base) / [double]$pick.base) * 100.0
      $exRows += ("| {0} | {1} | {2} | {3} |" -f $pick.name, (Format-Won $weekly.close), (Format-Pct $retPct), 'weekly_close_at_or_below_stop_loss')
    }
    $excludedBlock = @"

| 종목 | 제외가 | 기준가 대비 | 사유 |
|------|--------|-------------|------|
$($exRows -join "`r`n")
"@
  } else {
    $excludedBlock = "`r`n- 해당 없음 (주간 종가가 손절가 이하로 내려간 종목 없음)`r`n"
  }

  $section = @"

## Week $($nextWeek): $weekStr

$MarketState
- (메모) 이번 주 관찰 포인트를 1~2줄로 요약. (예: 반도체 주도/외국인 매도 vs 기관 매수 등)

### Active 업데이트 (주간 종가 기준)

| 종목 | 주간 종가($weekStr) | 누적수익률 | 목표달성률 | 외국인/기관 수급(주간) | 모멘텀(요약) | 판단 |
|------|----------------------|------------|------------|-------------------------|--------------|------|
$($rows -join "`r`n")

### 손절 제외
$excludedBlock

### 다음 주 체크포인트

- 공통: 손절가(종가 기준) 이탈 여부 최우선.
- 수급: 외국인/기관 주간 흐름 변화(전환/확대/축소).
- 모멘텀: RSI 과열/둔화 및 52주 고점 재시험 구간의 변동성.

출처:
- (예시) 한국경제/네이버금융/인베스팅/AlphaSquare 등 + 확인일 기입
"@

  return ($TrackingMarkdown.TrimEnd() + $section + "`r`n")
}

function Update-PlaybookForFlowMomentum {
  param(
    [string]$PlaybookMarkdown,
    [hashtable]$PickByTicker,
    [hashtable]$WeeklyByTicker,
    [datetime]$WeekCloseDate,
    [datetime]$NowLocal
  )

  $asOf = $NowLocal.ToString('yyyy-MM-dd')
  $weekStr = $WeekCloseDate.ToString('yyyy-MM-dd')

  $text = $PlaybookMarkdown
  $text = [regex]::Replace($text, '^(기준일:\s*).*$',
    ('$1{0} KST' -f $asOf),
    [System.Text.RegularExpressions.RegexOptions]::Multiline
  )
  $text = [regex]::Replace($text, '^(가격 기준:\s*).*$',
    ('$1{0} 종가 (주간 마감)' -f $weekStr),
    [System.Text.RegularExpressions.RegexOptions]::Multiline
  )

  $flowTickers = @('000660','005930','018260') | Where-Object { $WeeklyByTicker.ContainsKey($_) -and $PickByTicker.ContainsKey($_) }
  foreach ($ticker in $flowTickers) {
    $pick = $PickByTicker[$ticker]
    $weekly = $WeeklyByTicker[$ticker]

    $rrDen = [double]([Math]::Max(1, ($weekly.close - $pick.stop)))
    $rrNum = [double]([Math]::Max(0, ($pick.target - $weekly.close)))
    $rr = $rrNum / $rrDen

    $nearTarget = ($pick.target - $weekly.close) / [double]$pick.target * 100.0
    $sizing = if ($nearTarget -le 3) { '최대 2~4% (목표 근접 구간은 보수적으로)' }
      elseif ($rr -ge 2.5) { '최대 3~5% (이론 Kelly의 1/4 이하 관찰 비중)' }
      elseif ($rr -ge 1.5) { '최대 2~4% (보수적 분할/관찰 비중)' }
      else { '최대 0~2% (손익비 불리 시 축소)' }

    $entryLow = [long]([Math]::Floor($weekly.close * 0.95))
    $entryHigh = [long]([Math]::Floor($weekly.close * 0.98))
    $addTrigger = if ($weekly.week52_high) { (Format-Won $weekly.week52_high) } else { '52주 고점' }

    $entryZone = ("현재가({0}) 대비 -2%~-5% 조정(대략 {1}~{2}) 후 종가 지지 + 수급 안정 시나리오, 또는 {3} 재돌파 후 2거래일 이상 안착" -f
      (Format-Won $weekly.close),
      (Format-Won $entryLow),
      (Format-Won $entryHigh),
      $addTrigger
    )
    $addZone = ("{0} 재돌파 후 거래량·수급 동반 안착(2거래일+) 시에만 '추세 확인'으로 격상" -f $addTrigger)
    $avoidZone = ("RSI(14) 70 상회 + {0} 부근에서 거래량 둔화가 겹치는 추격 구간" -f $addTrigger)
    $exitPlan = ("목표가({0}) 접근/도달 시 변동성 확대(윗꼬리/거래량 둔화) 여부를 우선 점검해 방어적 분할 축소/추세 보유를 재평가" -f (Format-Won $pick.target))
    $invalidation = ("주간 종가가 손절가({0}) 이하로 내려가거나, 외국인·기관 흐름이 2주 연속 동반 악화되며 추세 회복 실패 시" -f (Format-Won $pick.stop))
    $weeklyMonitoring = ("(1) 주간 종가 기준 손절가({0}) 방어 (2) 외국인/기관 주간 순매수 전환/확대 여부 (3) {1} 재시험 구간의 변동성" -f (Format-Won $pick.stop), $addTrigger)

    $sectionHeader = ("## {0} ({1})" -f [regex]::Escape($pick.name), $ticker)
    $pattern = "(?ms)^(##\s+$([regex]::Escape($pick.name))\s+\($ticker\)\s*\r?\n)(.*?)(?=^##\s+|\z)"
    $text = [regex]::Replace($text, $pattern, {
      param($m)
      $header = $m.Groups[1].Value
      $body = $m.Groups[2].Value

      $body = [regex]::Replace($body, '^- entry_zone:.*$', ('- entry_zone: {0}' -f $entryZone), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- add_zone:.*$', ('- add_zone: {0}' -f $addZone), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- avoid_zone:.*$', ('- avoid_zone: {0}' -f $avoidZone), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- stop_loss:.*$', ('- stop_loss: {0} 종가 이탈 시 추적 제외/전략 무효화' -f (Format-Won $pick.stop)), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- exit_plan:.*$', ('- exit_plan: {0}' -f $exitPlan), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- invalidation:.*$', ('- invalidation: {0}' -f $invalidation), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- Kelly-style sizing:.*$', ('- Kelly-style sizing: {0}' -f $sizing), [System.Text.RegularExpressions.RegexOptions]::Multiline)
      $body = [regex]::Replace($body, '^- weekly_monitoring:.*$', ('- weekly_monitoring: {0}' -f $weeklyMonitoring), [System.Text.RegularExpressions.RegexOptions]::Multiline)

      return ($header + $body)
    }, [System.Text.RegularExpressions.RegexOptions]::Multiline)

    # Update the summary table row (only if it exists).
    $summaryRowPattern = "(?m)^\\|\\s*$([regex]::Escape($pick.name))\\s*\\|.*\\|$"
    if ($text -match $summaryRowPattern) {
      $text = [regex]::Replace($text, $summaryRowPattern, {
        param($m)
        $stopLossText = Format-Won $pick.stop
        $exitPlanShort = ("{0} 접근 시 변동성 점검 / {1} 도달 시 재평가" -f (Format-Won $pick.target), (Format-Won $pick.target))
        return ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f
          $pick.name,
          $(if ($nearTarget -le 3) { 'B: Probe only (목표 근접)' } else { 'A: Wait for pullback' }),
          ("현재가 대비 -2%~-5% 조정 후 지지, 또는 {0} 재돌파" -f $addTrigger),
          $stopLossText,
          $exitPlanShort,
          $sizing
        )
      })
    }
  }

  return $text
}

$sourcePortfolio = Resolve-WorkspacePath $SourcePortfolioPath
$trackingFile = Resolve-WorkspacePath $TrackingPath
$playbookFile = Resolve-WorkspacePath $PlaybookPath

foreach ($required in @($sourcePortfolio, $trackingFile, $playbookFile)) {
  if (-not (Test-Path $required)) {
    throw "Missing required file: $required"
  }
}

$weekCloseDate = Get-LatestCompletedWeekCloseDate -NowLocal $Now
$weekCloseStr = $weekCloseDate.ToString('yyyy-MM-dd')
$reviewDate = $Now.ToString('yyyy-MM-dd')

Write-Output '== Weekly Flow Momentum update =='
Write-Output ("Now: {0}" -f $Now.ToString('yyyy-MM-dd HH:mm:ss K'))
Write-Output ("Latest completed week close (KRX): {0}" -f $weekCloseStr)

$portfolioText = Get-Content -Path $sourcePortfolio -Raw -Encoding UTF8
$picks = Get-FlowMomentumPickTable -Markdown $portfolioText
$pickByTicker = @{}
foreach ($pick in $picks) {
  $pickByTicker[$pick.ticker] = $pick
}

$trackingText = Get-Content -Path $trackingFile -Raw -Encoding UTF8
$activeTickers = Get-ActiveTrackingTickers -TrackingMarkdown $trackingText
$activeTickers = @($activeTickers | Where-Object { $pickByTicker.ContainsKey($_) })

if ($activeTickers.Count -eq 0) {
  throw "No active tickers found in Active Tracking table."
}

$weeklyByTicker = Read-WeeklyData -Tickers $activeTickers -PickByTicker $pickByTicker -WeekCloseDate $weekCloseDate -DataPathValue $DataPath -NoPromptValue:$NoPrompt

$moved = Move-StopLossExclusions -TrackingMarkdown $trackingText -PickByTicker $pickByTicker -WeeklyByTicker $weeklyByTicker -ExcludeDate $reviewDate
$trackingText = $moved.markdown

$trackingText = Update-ActiveTrackingTable -TrackingMarkdown $trackingText -PickByTicker $pickByTicker -WeeklyByTicker $weeklyByTicker -ReviewDate $reviewDate
$trackingText = Append-WeeklySection -TrackingMarkdown $trackingText -WeekCloseDate $weekCloseDate -PickByTicker $pickByTicker -WeeklyByTicker $weeklyByTicker -ExcludedTickers $moved.excluded

if ($DryRun) {
  Write-Output ("DRY  would update tracking: {0}" -f $TrackingPath)
} else {
  Set-Content -Path $trackingFile -Value $trackingText -Encoding UTF8
  Write-Output ("OK   updated tracking: {0}" -f $TrackingPath)
}

$playbookText = Get-Content -Path $playbookFile -Raw -Encoding UTF8
$playbookText = Update-PlaybookForFlowMomentum -PlaybookMarkdown $playbookText -PickByTicker $pickByTicker -WeeklyByTicker $weeklyByTicker -WeekCloseDate $weekCloseDate -NowLocal $Now
if ($DryRun) {
  Write-Output ("DRY  would update playbook: {0}" -f $PlaybookPath)
} else {
  Set-Content -Path $playbookFile -Value $playbookText -Encoding UTF8
  Write-Output ("OK   updated playbook: {0}" -f $PlaybookPath)
}

Write-Output ''
Write-Output '== Post steps =='
Write-Output '1) Review appended Week section sources + market_state text.'
Write-Output '2) Run: powershell -ExecutionPolicy Bypass -File scripts/validate_project.ps1'
Write-Output '3) Run: powershell -ExecutionPolicy Bypass -File scripts/review_changes.ps1'
Write-Output '4) Decide commit vs revert for non-tracking files.'
