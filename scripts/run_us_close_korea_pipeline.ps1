param(
  [switch]$OfflineSample
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$envFile = Join-Path $projectRoot ".env.local"
$alertsFile = Join-Path $projectRoot "picks/alerts/pending.json"

Write-Host "=== [START] US Close Korea Preopen Analysis Pipeline ===" -ForegroundColor Cyan

# Pipeline Stages
$stages = @(
  [PSCustomObject]@{ Step = 1; Name = "Kiwoom Token Refresh"; Status = "PENDING"; Error = "" },
  [PSCustomObject]@{ Step = 2; Name = "US Close Data & Mapping"; Status = "PENDING"; Error = "" },
  [PSCustomObject]@{ Step = 3; Name = "Korean Market Prices"; Status = "PENDING"; Error = "" },
  [PSCustomObject]@{ Step = 4; Name = "Kiwoom Foreign Flows"; Status = "PENDING"; Error = "" },
  [PSCustomObject]@{ Step = 5; Name = "Preopen Candidate Filter"; Status = "PENDING"; Error = "" },
  [PSCustomObject]@{ Step = 6; Name = "System Integrity Validation"; Status = "PENDING"; Error = "" },
  [PSCustomObject]@{ Step = 7; Name = "Obsidian & Metacognitive Scan"; Status = "PENDING"; Error = "" }
)

# 1. Kiwoom Token Refresh
Write-Host "`n[1/7] Refreshing Kiwoom OpenAPI Token..." -ForegroundColor Yellow
try {
    python (Join-Path $scriptDir "refresh_kiwoom_token.py")
    if ($LASTEXITCODE -ne 0) { throw "Token refresh script returned exit code $LASTEXITCODE" }
    Write-Host "[OK] Token refresh success" -ForegroundColor Green
    $stages[0].Status = "SUCCESS"
} catch {
    Write-Host "[ERROR] Token refresh failed: $_" -ForegroundColor Red
    $stages[0].Status = "FAILED"
    $stages[0].Error = $_.Exception.Message
}

# Load credentials from .env.local
$envLocal = @{}
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)\s*=\s*(.*)$') {
            $envLocal[$Matches[1].Trim()] = $Matches[2].Trim().Trim('"').Trim("'")
        }
    }
}

# 2. Collect US Close Data & Map Sectors
Write-Host "`n[2/7] Collecting US Close Data & Mapping Sectors..." -ForegroundColor Yellow
try {
    $usCloseArgs = @((Join-Path $scriptDir "collect_us_close_data.py"))
    if ($OfflineSample) {
        $usCloseArgs += "--offline-sample"
    }
    python @usCloseArgs
    if ($LASTEXITCODE -ne 0) { throw "US close script returned exit code $LASTEXITCODE" }
    Write-Host "[OK] US close data collection completed" -ForegroundColor Green
    $stages[1].Status = "SUCCESS"
} catch {
    Write-Host "[ERROR] US close data collection failed: $_" -ForegroundColor Red
    $stages[1].Status = "FAILED"
    $stages[1].Error = $_.Exception.Message
}

# 3. Collect Korean Market Prices
Write-Host "`n[3/7] Collecting Korean Market Price Data..." -ForegroundColor Yellow
try {
    python (Join-Path $scriptDir "collect_market_data.py")
    if ($LASTEXITCODE -ne 0) { throw "Collect market data script returned exit code $LASTEXITCODE" }
    Write-Host "[OK] Korean market price collection completed" -ForegroundColor Green
    $stages[2].Status = "SUCCESS"
} catch {
    Write-Host "[ERROR] Korean market price collection failed: $_" -ForegroundColor Red
    $stages[2].Status = "FAILED"
    $stages[2].Error = $_.Exception.Message
}

# 4. Collect Kiwoom Foreign Flows
Write-Host "`n[4/7] Collecting Kiwoom Foreign Net Buying Flows..." -ForegroundColor Yellow
try {
    $token = $envLocal['KIWOOM_ACCESS_TOKEN']
    $appKey = $envLocal['KIWOOM_APP_KEY']
    $appSecret = $envLocal['KIWOOM_APP_SECRET']
    if ($token -and $appKey -and $appSecret) {
        $flowArgs = @((Join-Path $scriptDir "collect_kiwoom_foreign_rank.py"), "--access-token", $token, "--app-key", $appKey, "--app-secret", $appSecret)
        if ($OfflineSample) {
            $flowArgs += "--offline-sample"
        }
        python @flowArgs
        if ($LASTEXITCODE -ne 0) { throw "Collect foreign rank script returned exit code $LASTEXITCODE" }
        Write-Host "[OK] Kiwoom foreign flows collection completed" -ForegroundColor Green
        $stages[3].Status = "SUCCESS"
    } else {
        Write-Host "[WARN] Missing credentials in .env.local, skipping foreign flow collection" -ForegroundColor Yellow
        $stages[3].Status = "SKIPPED"
        $stages[3].Error = "Missing credentials in .env.local"
    }
} catch {
    Write-Host "[ERROR] Foreign flows collection failed: $_" -ForegroundColor Red
    $stages[3].Status = "FAILED"
    $stages[3].Error = $_.Exception.Message
}

# 5. Run Preopen Filter
Write-Host "`n[5/7] Filtering Preopen Candidates & Calculating Risks..." -ForegroundColor Yellow
try {
    $filterArgs = @((Join-Path $scriptDir "run_preopen_filter.py"))
    if ($OfflineSample) {
        $filterArgs += "--offline-sample"
    }
    python @filterArgs
    if ($LASTEXITCODE -ne 0) { throw "Run preopen filter script returned exit code $LASTEXITCODE" }
    Write-Host "[OK] Preopen candidates filtering completed" -ForegroundColor Green
    $stages[4].Status = "SUCCESS"
} catch {
    Write-Host "[ERROR] Preopen candidate filtering failed: $_" -ForegroundColor Red
    $stages[4].Status = "FAILED"
    $stages[4].Error = $_.Exception.Message
}

# 6. System Integrity Validation
Write-Host "`n[6/7] Validating Project Integrity & Reports..." -ForegroundColor Yellow
try {
    & (Join-Path $scriptDir "validate_project.ps1")
    # No $LASTEXITCODE check needed for direct script block/function invocation; exceptions are caught directly by catch block.
    Write-Host "[OK] Project integrity validation completed" -ForegroundColor Green
    $stages[5].Status = "SUCCESS"
} catch {
    Write-Host "[ERROR] Project integrity validation failed: $_" -ForegroundColor Red
    $stages[5].Status = "FAILED"
    $stages[5].Error = $_.Exception.Message
}

# 7. Obsidian & Metacognitive Scan
Write-Host "`n[7/7] Scanning Obsidian Vault Hygiene & Metacognitive Activity..." -ForegroundColor Yellow
try {
    Write-Host "  - Scanning Obsidian Vault Hygiene..." -ForegroundColor Gray
    python (Join-Path $scriptDir "validate_obsidian_vault.py")
    if ($LASTEXITCODE -ne 0) { throw "validate_obsidian_vault.py returned exit code $LASTEXITCODE" }
    
    Write-Host "  - Analyzing Real-time Market Leaders..." -ForegroundColor Gray
    $leaderArgs = @((Join-Path $scriptDir "analyze_realtime_leaders.py"))
    if ($OfflineSample) {
        $leaderArgs += "--test"
    }
    python @leaderArgs
    if ($LASTEXITCODE -ne 0) { throw "analyze_realtime_leaders.py returned exit code $LASTEXITCODE" }

    Write-Host "  - Analyzing Metacognitive logs and updating dashboard..." -ForegroundColor Gray
    python (Join-Path $scriptDir "monitor_metadata_activity.py")
    if ($LASTEXITCODE -ne 0) { throw "monitor_metadata_activity.py returned exit code $LASTEXITCODE" }
    
    Write-Host "[OK] Obsidian verification and metacognitive scan completed" -ForegroundColor Green
    $stages[6].Status = "SUCCESS"
} catch {
    Write-Host "[ERROR] Obsidian and Metacognitive scan failed: $_" -ForegroundColor Red
    $stages[6].Status = "FAILED"
    $stages[6].Error = $_.Exception.Message
}

# Final Summary Report
Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "[SUMMARY] Pipeline Stages Summary" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

foreach ($stage in $stages) {
    $color = "Green"
    if ($stage.Status -eq "FAILED") { $color = "Red" }
    elseif ($stage.Status -eq "SKIPPED" -or $stage.Status -eq "PENDING") { $color = "Yellow" }
    
    $stepStr = "[Step $($stage.Step)] $($stage.Name.PadRight(30)) : "
    Write-Host $stepStr -NoNewline -ForegroundColor White
    Write-Host $stage.Status -ForegroundColor $color
    if ($stage.Error) {
        Write-Host "  └ Reason: $($stage.Error)" -ForegroundColor DarkGray
    }
}

# Active Alerts Check
Write-Host "`n--------------------------------------------------" -ForegroundColor Cyan
Write-Host "[ALERTS] Real-time Active Issues & Alerts (pending.json)" -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan

if (Test-Path $alertsFile) {
    try {
        $alertsJson = Get-Content $alertsFile -Raw | ConvertFrom-Json
        if ($alertsJson.issues -and $alertsJson.issues.Count -gt 0) {
            Write-Host "Total $($alertsJson.issues.Count) issues/alerts are active:" -ForegroundColor Yellow
            foreach ($issue in $alertsJson.issues) {
                $sevColor = "Red"
                if ($issue.severity -eq "WARN" -or $issue.severity -eq "YELLOW") { $sevColor = "Yellow" }
                Write-Host "  [$($issue.severity)] " -NoNewline -ForegroundColor $sevColor
                Write-Host "$($issue.date) - $($issue.name)($($issue.ticker)): $($issue.message)" -ForegroundColor White
            }
        } else {
            Write-Host "[CLEAN] No active real-time issues/alerts detected." -ForegroundColor Green
        }
    } catch {
        Write-Host "[WARN] Failed to read or parse pending.json: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[CLEAN] No active real-time issues/alerts detected." -ForegroundColor Green
}

# Metacognitive Scan Results Check
Write-Host "`n--------------------------------------------------" -ForegroundColor Cyan
Write-Host "[METACOGNITION] Metacognitive Log Summary & Actions" -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan

$metaActivityFile = Join-Path $projectRoot "picks/alerts/metacognitive_activity.json"
if (Test-Path $metaActivityFile) {
    try {
        $metaJson = Get-Content $metaActivityFile -Raw | ConvertFrom-Json
        $scannedMsg = "Total files scanned: " + $metaJson.scanned_files_count
        Write-Host $scannedMsg -ForegroundColor White
        $recentMsg = "Recent 24h activity logs: " + $metaJson.recent_activity_count
        Write-Host $recentMsg -ForegroundColor White
        
        $highPriorityCount = $metaJson.high_priority_count
        if ($highPriorityCount -gt 0) {
            $alertMsg = "[ALERT] High priority action items detected: " + $highPriorityCount
            Write-Host $alertMsg -ForegroundColor Red
            foreach ($item in $metaJson.high_priority_items) {
                $tickStr = ""
                if ($item.ticker) {
                    $tickStr = "(" + $item.ticker + ")"
                }
                $msg = "  - [HIGH] " + $item.file_name + $tickStr + ": " + $item.reason + " (Mtime: " + $item.modified_time + ")"
                Write-Host $msg -ForegroundColor Yellow
            }
            $resolvedDashboardPath = (Resolve-Path (Join-Path $projectRoot 'obsidian/stock_log/09_decision_journal/metacognitive_dashboard.md')).Path.Replace('\','/')
            $linkMsg = "Dashboard Link: file:///" + $resolvedDashboardPath
            Write-Host $linkMsg -ForegroundColor Gray
        } else {
            Write-Host "[CLEAN] No high priority system action items detected." -ForegroundColor Green
        }
    } catch {
        $errStr = $_.Exception.Message
        Write-Host ("[WARN] metacognitive_activity.json parse error: " + $errStr) -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] Metacognitive activity JSON file not found." -ForegroundColor Yellow
}
Write-Host "==================================================" -ForegroundColor Cyan
