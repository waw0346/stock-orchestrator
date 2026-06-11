param(
  [switch]$Install,
  [switch]$DryRun,
  [switch]$Json
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $root 'scripts/bootstrap.py'

$argsList = @($script)
if ($Install) {
  $argsList += '--install'
}
if ($DryRun) {
  $argsList += '--dry-run'
}
if ($Json) {
  $argsList += '--json'
}

python @argsList
exit $LASTEXITCODE
