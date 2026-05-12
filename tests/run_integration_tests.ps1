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
  '@entry-exit-timing-strategist'
)

Assert-FileContains 'README.md' @(
  'flow-momentum-tracker',
  'tracking_weekly_cumulative_flow_momentum.md',
  'entry-exit-timing-strategist'
)

Assert-FileContains 'scripts/validate_project.ps1' @(
  'Flow/Momentum tracking',
  'tracking_weekly_cumulative_flow_momentum.md',
  'Entry/Exit timing',
  'Paper trading'
)

Assert-FileContains 'docs/paper_trading_options.md' @(
  'KIS Developers',
  'KIS_ACCOUNT_TYPE=VIRTUAL',
  'paper_trade_simulator.ps1',
  'paper'
)

Write-Output 'integration tests passed'
