$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$testFile = Join-Path $root 'tests/test_kiwoom_rest_client.py'

Set-Location $root
python $testFile
if ($LASTEXITCODE -ne 0) {
  throw "Kiwoom REST client tests failed"
}

Write-Output 'kiwoom rest client tests passed'
