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

function Normalize-PickStatus {
  param([string]$Status)

  if ([string]::IsNullOrWhiteSpace($Status)) {
    return ''
  }
  if ($Status -match '^(active|watch|closed|completed|blocked)') {
    return $matches[1]
  }
  return $Status.Trim()
}

function Get-GitStatusLines {
  Push-Location $root
  try {
    return @(git status --short)
  } finally {
    Pop-Location
  }
}

Write-Output '== Change review =='
$statusLines = Get-GitStatusLines
if ($statusLines.Count -eq 0) {
  Write-Output 'OK   working tree clean'
} else {
  foreach ($line in $statusLines) {
    Write-Output ("CHG  {0}" -f $line)
  }
}

Write-Output ''
Write-Output '== Change classification =='
$criticalPatterns = @(
  '^CLAUDE\.md$',
  '^README\.md$',
  '^CURRENT_STATE\.md$',
  '^AGENTS\.md$',
  '^\.gitignore$',
  '^\.mcp\.json$',
  '^\.github/workflows/.*\.yml$',
  '^INVESTMENT_POLICY\.md$',
  '^docs/pre_trade_checklist\.md$',
  '^docs/(ai_runtime_adapter|context_summary|scripts_lib_refactor_candidates)\.md$',
  '^scripts/(bootstrap|summarize_context)\.(py|ps1)$',
  '^scripts/lib/.*\.py$',
  '^scripts/(validate_project|review_changes)\.ps1$',
  '^tests/.*\.ps1$',
  '^tests/run_cross_platform_smoke\.py$',
  '^tests/run_all_tests\.ps1$',
  '^\.claude/agents/(market-regime-analyst|portfolio-manager|position-sizing-analyst|performance-reviewer|us-close-korea-strategist)\.md$'
)
$archivedDocPatterns = @(
  '^(README_v2|CLAUDE_v2|00_setup_guide|01_project_instructions)\.md$'
)
$operatingDataPatterns = @(
  '^picks/20.*\.md$',
  '^picks/INDEX\.md$',
  '^picks/WATCHLIST\.md$',
  '^picks/dashboard\.html$',
  '^picks/paper_price_snapshot\.json$',
  '^picks/tracking_.*\.md$',
  '^picks/entry_exit_timing_playbook.*\.md$',
  '^picks/postmortems/.*'
)
$localNoisePatterns = @(
  '^\.claude/settings\.local\.json$',
  '^\.claude/agents/.*\.test$',
  '^picks/cache/.*\.json$',
  '^picks/alerts/.*\.json$',
  '^.*\.test$',
  '^.*\.test\.(json|csv)$'
)

foreach ($line in $statusLines) {
  $changeCode = $line.Substring(0, 2)
  $path = $line.Substring(3).Trim()
  $normalized = $path -replace '\\', '/'
  if ($normalized -eq 'scripts/lib/') {
    $normalized = 'scripts/lib'
  }
  if ($localNoisePatterns | Where-Object { $normalized -match $_ }) {
    if ($changeCode -match 'D') {
      Write-Output ("OK   local/transient cleanup {0}" -f $path)
    } else {
      Add-Issue -Level 'WARN' -Area 'Change classification' -Message ("Local/transient file should not be committed: {0}" -f $path)
      Write-Output ("WARN local/transient {0}" -f $path)
    }
  } elseif ($criticalPatterns | Where-Object { $normalized -match $_ }) {
    Write-Output ("OK   governance change {0}" -f $path)
  } elseif ($normalized -eq 'scripts/lib') {
    Write-Output ("OK   governance change {0}" -f $path)
  } elseif ($archivedDocPatterns | Where-Object { $normalized -match $_ }) {
    Write-Output ("OK   archived guidance marker {0}" -f $path)
  } elseif ($operatingDataPatterns | Where-Object { $normalized -match $_ }) {
    Write-Output ("OK   operating data {0}" -f $path)
  } else {
    Write-Output ("INFO other change {0}" -f $path)
  }
}

Write-Output ''
Write-Output '== Archived file guard =='
$archivedFiles = @('README_v2.md', 'CLAUDE_v2.md', '00_setup_guide.md', '01_project_instructions.md')
$stalePatterns = @('path/to/stock', 'stock-analyst-agent', 'memory: project')
foreach ($relative in $archivedFiles) {
  $path = Join-Path $root $relative
  if (-not (Test-Path $path)) {
    Add-Issue -Level 'ERROR' -Area 'Archived file guard' -Message ("Missing archived marker file: {0}" -f $relative)
    Write-Output ("FAIL missing {0}" -f $relative)
    continue
  }
  $text = Get-Content -Path $path -Raw -Encoding UTF8
  if ($text -notmatch '^# ARCHIVED') {
    Add-Issue -Level 'ERROR' -Area 'Archived file guard' -Message ("Archived file missing ARCHIVED header: {0}" -f $relative)
    Write-Output ("FAIL archived header {0}" -f $relative)
  }
  foreach ($pattern in $stalePatterns) {
    if ($text -match [regex]::Escape($pattern)) {
      Add-Issue -Level 'ERROR' -Area 'Archived file guard' -Message ("Archived file still contains stale active guidance: {0} pattern={1}" -f $relative, $pattern)
      Write-Output ("FAIL stale archived text {0} pattern={1}" -f $relative, $pattern)
    }
  }
}

Write-Output ''
Write-Output '== Pick risk guard =='
$pickDir = Join-Path $root 'picks'
$indexFile = Join-Path $pickDir 'INDEX.md'
$indexText = if (Test-Path $indexFile) { Get-Content -Path $indexFile -Raw -Encoding UTF8 } else { '' }

foreach ($pick in Get-ChildItem -Path $pickDir -Filter '20*.md') {
  $fm = Read-FrontMatter -Path $pick.FullName
  $ticker = $fm['ticker']
  if ([string]::IsNullOrWhiteSpace($ticker)) {
    continue
  }

  $rawStatus = $fm['status']
  $status = Normalize-PickStatus $rawStatus
  $name = $fm['name']
  $text = Get-Content -Path $pick.FullName -Raw -Encoding UTF8

  if ($status -notin @('active', 'watch', 'closed', 'completed')) {
    Add-Issue -Level 'ERROR' -Area 'Pick risk guard' -Message ("Unknown pick status: {0} {1} status={2}" -f $ticker, $name, $rawStatus)
    Write-Output ("FAIL {0} {1} unknown status {2}" -f $ticker, $name, $rawStatus)
  }

  if ($status -eq 'active' -and $text -match 'Critical' -and $text -notmatch 'Capital Protection Gate') {
    Add-Issue -Level 'WARN' -Area 'Pick risk guard' -Message ("Active pick has Critical risk text but no Capital Protection Gate section: {0} {1}" -f $ticker, $name)
    Write-Output ("WARN {0} {1} active critical risk without Capital Protection Gate" -f $ticker, $name)
  }

  if ($indexText -notmatch [regex]::Escape($ticker)) {
    Add-Issue -Level 'ERROR' -Area 'Pick risk guard' -Message ("Pick missing from INDEX.md: {0} {1}" -f $ticker, $name)
    Write-Output ("FAIL {0} {1} missing from INDEX" -f $ticker, $name)
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
