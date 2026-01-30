param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Bash = $null

$Candidates = @(
  "C:\\Program Files\\Git\\bin\\bash.exe",
  "C:\\Program Files\\Git\\usr\\bin\\bash.exe"
)
foreach ($c in $Candidates) {
  if (Test-Path $c) { $Bash = $c; break }
}
if (-not $Bash) {
  $cmd = Get-Command bash -ErrorAction SilentlyContinue
  if ($cmd) { $Bash = $cmd.Source }
}

if (-not $Bash) {
  Write-Error "bash.exe not found. Install Git for Windows and re-run."
  exit 1
}

$ArgString = $Args -join ' '
& $Bash -lc "\"$Root/devhost\" $ArgString"