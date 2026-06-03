param(
  [string]$SnapshotPath = '',
  [string]$CandidatesPath = '',
  [switch]$OfflineSample
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/collect_us_close_data.py'

$argsList = @($script)
if (-not [string]::IsNullOrWhiteSpace($SnapshotPath)) {
  $argsList += @('--snapshot-path', $SnapshotPath)
}
if (-not [string]::IsNullOrWhiteSpace($CandidatesPath)) {
  $argsList += @('--candidates-path', $CandidatesPath)
}
if ($OfflineSample) {
  $argsList += '--offline-sample'
}

python @argsList
exit $LASTEXITCODE
