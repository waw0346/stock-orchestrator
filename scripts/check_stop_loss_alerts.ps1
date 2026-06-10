<#
.SYNOPSIS
  주식 추천픽들의 손절선(Stop-Loss) 이탈 여부를 실시간/스냅샷 기반으로 체크하고 경고를 발행하는 스크립트.
.PARAMETER DryRun
  모의 시뮬레이션 모드를 활성화하여 가상의 손절 이탈 및 근접 상황을 체크합니다.
.PARAMETER WriteAlerts
  DryRun 모드 중 실제로 경보를 pending.json 파일에 기록할지 여부.
#>
param(
    [switch]$DryRun,
    [switch]$WriteAlerts
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonScript = Join-Path $PSScriptRoot "check_stop_loss_alerts.py"

$ArgsList = @()
if ($DryRun) { $ArgsList += "--DryRun" }
if ($WriteAlerts) { $ArgsList += "--WriteAlerts" }

python $PythonScript $ArgsList
