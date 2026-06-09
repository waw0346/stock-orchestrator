<#
.SYNOPSIS
    ClaudeSlim 로컬 프록시 시작 스크립트
    Claude Code API 호출을 압축해 토큰 사용량을 60~85% 절감합니다.

.DESCRIPTION
    실행 후 Claude Code 세션에서 ANTHROPIC_BASE_URL=http://localhost:8086 이 자동 설정됩니다.
    프록시를 종료하면 Claude Code는 자동으로 직접 연결로 복귀합니다.

.EXAMPLE
    # 기본 실행 (새 창에서 프록시 시작 후 Claude Code 실행)
    .\scripts\start_claudeslim.ps1

    # 통계 확인 (프록시 실행 중)
    curl http://localhost:8086/stats

    # 상태 확인
    curl http://localhost:8086/health
#>

$ClaudeSlimExe = "$env:APPDATA\Python\Python314\Scripts\claudeslim.exe"
$ProxyUrl = "http://localhost:8086"

Write-Host "🚀 ClaudeSlim 프록시 시작..." -ForegroundColor Cyan

# claudeslim.exe 경로 확인
if (-not (Test-Path $ClaudeSlimExe)) {
    # PATH에서 찾기
    $found = Get-Command claudeslim -ErrorAction SilentlyContinue
    if ($found) {
        $ClaudeSlimExe = $found.Source
    } else {
        Write-Host "❌ claudeslim을 찾을 수 없습니다. 다음 명령으로 설치하세요:" -ForegroundColor Red
        Write-Host "   pip install claudeslim" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "📍 실행 경로: $ClaudeSlimExe" -ForegroundColor Gray

# 이미 실행 중인지 확인
try {
    $health = Invoke-RestMethod -Uri "$ProxyUrl/health" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "ℹ️  ClaudeSlim이 이미 실행 중입니다 ($ProxyUrl)" -ForegroundColor Yellow
} catch {
    # 새 창에서 프록시 시작
    Start-Process -FilePath $ClaudeSlimExe -WindowStyle Normal
    Write-Host "⏳ 프록시 초기화 대기 중..." -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

# 환경변수 설정 (현재 세션)
$env:ANTHROPIC_BASE_URL = $ProxyUrl
Write-Host "✅ ANTHROPIC_BASE_URL=$ProxyUrl 설정 완료" -ForegroundColor Green

# 상태 확인
try {
    $health = Invoke-RestMethod -Uri "$ProxyUrl/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "✅ ClaudeSlim 정상 작동 중" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 이제 이 터미널에서 'claude' 명령을 실행하면 압축이 자동 적용됩니다." -ForegroundColor Cyan
    Write-Host "📊 통계 확인: curl http://localhost:8086/stats" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  프록시 응답 없음 — claudeslim 창을 확인하세요." -ForegroundColor Yellow
}
