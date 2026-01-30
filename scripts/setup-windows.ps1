param(
  [switch]$InstallCaddy,
  [switch]$InstallShim
)

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Resolve-Path (Join-Path $RootDir "..")

Write-Host "Devhost Windows setup"

function Get-Python {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return "py -3" }
  return $null
}

$PythonCmd = Get-Python
if (-not $PythonCmd) {
  Write-Error "Python not found. Install Python 3.x and re-run."
  exit 1
}

$VenvDir = Join-Path $RepoDir "router\venv"
$ReqFile = Join-Path $RepoDir "router\requirements.txt"

Write-Host "[+] Creating venv at $VenvDir"
if (-not (Test-Path $VenvDir)) {
  if ($PythonCmd -eq "py -3") {
    & py -3 -m venv $VenvDir
  } else {
    & $PythonCmd -m venv $VenvDir
  }
}

$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Write-Error "Venv python not found at $VenvPy"
  exit 1
}

Write-Host "[+] Installing router requirements"
& $VenvPy -m pip install -r $ReqFile

$ConfigFile = Join-Path $RepoDir "devhost.json"
if (-not (Test-Path $ConfigFile)) {
  "{}" | Out-File -Encoding utf8 $ConfigFile
}

$CaddyFile = Join-Path $RepoDir "caddy\Caddyfile"
$CaddyTemplate = Join-Path $RepoDir "caddy\Caddyfile.template"
if (-not (Test-Path $CaddyFile)) {
  Copy-Item $CaddyTemplate $CaddyFile
}

if ($InstallCaddy) {
  if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      Write-Host "[+] Installing Caddy via winget"
      winget install -e --id Caddy.Caddy
    } else {
      Write-Warning "winget not found; install Caddy manually: https://caddyserver.com/docs/install"
    }
  }
}

if ($InstallShim) {
  $Shim = Join-Path $RepoDir "devhost.ps1"
  if (-not (Test-Path $Shim)) {
    Write-Warning "devhost.ps1 shim not found in repo."
  }
}

Write-Host "\nNext steps:" 
Write-Host "1) Install Caddy (if not already) and run it with: caddy run --config $CaddyFile"
Write-Host "2) Start the router: $VenvPy -m uvicorn app:app --host 127.0.0.1 --port 5555 --reload"
Write-Host "3) Use the CLI (Git Bash): ./devhost add <name> <port>"
Write-Host "   Or PowerShell shim: .\devhost.ps1 add <name> <port>"