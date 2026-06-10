<#
.SYNOPSIS
  손실률 15% 이상 대형 손실 종목에 대한 감리반 복기 파일(Postmortem Draft)을 자동 생성하는 스크립트.
.PARAMETER DryRun
  실제 파일을 작성하지 않고 감리 대상 종목만 스캔하여 보여줍니다.
#>
param(
    [switch]$DryRun
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonScript = Join-Path $PSScriptRoot "run_postmortem_audit.py"

$ArgsList = @()
if ($DryRun) { $ArgsList += "--DryRun" }

python $PythonScript $ArgsList
