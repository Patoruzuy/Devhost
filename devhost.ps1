param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ArgsList
)

$ScriptPath = Join-Path $PSScriptRoot "devhost"
if (-not (Test-Path $ScriptPath)) {
  Write-Error "devhost script not found at $ScriptPath"
  exit 1
}

$Python = $null
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { $Python = $cmd.Source }

if (-not $Python) {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    & $py.Source -3 $ScriptPath @ArgsList
    exit $LASTEXITCODE
  }
}

if (-not $Python) {
  Write-Error "Python not found. Install Python 3.x or ensure it is on PATH."
  exit 1
}

& $Python $ScriptPath @ArgsList
exit $LASTEXITCODE
