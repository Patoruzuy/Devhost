param(
  [switch]$InstallCaddy,
  [switch]$InstallShim,
  [switch]$Clean
)

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Resolve-Path (Join-Path $RootDir "..")

Write-Host "Devhost Windows setup" -ForegroundColor Cyan

function Get-Python {
  $candidates = @(
    @{ Cmd = 'py'; Args = @('-3') },
    @{ Cmd = 'python'; Args = @() }
  )
  foreach ($c in $candidates) {
    $cmd = Get-Command $c.Cmd -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    try {
      $exe = & $c.Cmd @($c.Args + @('-c','import sys; print(sys.executable)')) 2>$null
      if ($exe -match '^[A-Za-z]:\\' -and (Test-Path $exe)) {
        return @{ Cmd = $exe; Args = @() }
      }
    } catch {
      continue
    }
  }
  return $null
}

$PythonCmd = Get-Python
if (-not $PythonCmd) {
  Write-Error "Python not found. Install Python 3.x and re-run."
  exit 1
}

$VenvDir = Join-Path $RepoDir "router\venv"
$ReqFile = Join-Path $RepoDir "router\requirements.txt"

if ($Clean) {
  $confirm = Read-Host "This will remove venv, devhost.json, caddy/Caddyfile, and .devhost. Continue? [y/N]"
  if (-not $confirm -or $confirm -notmatch '^[Yy]$') { exit 0 }
  $pidFile = Join-Path $RepoDir ".devhost\router.pid"
  if (Test-Path $pidFile) {
    $pidValue = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($pidValue) { Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
  }
  $caddyProc = Get-Process caddy -ErrorAction SilentlyContinue
  if ($caddyProc) {
    $stopCaddy = Read-Host "Caddy is running. Stop it now? [y/N]"
    if ($stopCaddy -and $stopCaddy -match '^[Yy]$') {
      $caddyProc | Stop-Process -Force -ErrorAction SilentlyContinue
    }
  }
  # Stop python processes using the venv (best-effort) before deletion
  $venvPy = Join-Path $VenvDir "Scripts\python.exe"
  if (Test-Path $venvPy) {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$VenvDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
  }
  Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
  if (Test-Path $VenvDir) {
    Write-Warning "Failed to remove venv folder. It may be in use. Close any Python/uvicorn processes and retry."
    Write-Host "Try manually removing it:" -ForegroundColor Yellow
    Write-Host "  Remove-Item -Recurse -Force `"$VenvDir`"" -ForegroundColor Green
    Write-Host "If it still fails, reboot Windows and retry -Clean." -ForegroundColor Yellow
    exit 1
  }
  Remove-Item -Force (Join-Path $RepoDir "devhost.json") -ErrorAction SilentlyContinue
  Remove-Item -Force (Join-Path $RepoDir "caddy\Caddyfile") -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force (Join-Path $RepoDir ".devhost") -ErrorAction SilentlyContinue
  Write-Host "Clean complete." -ForegroundColor Green
  $cont = Read-Host "Continue with setup? [Y/n]"
  if ($cont -and $cont -notmatch '^[Yy]$') { exit 0 }
}

Write-Host "[+] Creating venv at $VenvDir"
$venvCfg = Join-Path $VenvDir "pyvenv.cfg"
if ((Test-Path $VenvDir) -and -not (Test-Path $venvCfg)) {
  $recreate = Read-Host "Existing venv is missing pyvenv.cfg. Recreate it? [Y/n]"
  if ($recreate -and $recreate -notmatch '^[Yy]$') {
    Write-Warning "Venv is invalid; aborting setup."
    exit 1
  }
  Write-Host "[!] Recreating venv..."
  $pidFile = Join-Path $RepoDir ".devhost\router.pid"
  if (Test-Path $pidFile) {
    $pidValue = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($pidValue) {
      Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
      Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
  }
  $venvPy = Join-Path $VenvDir "Scripts\python.exe"
  if (Test-Path $venvPy) {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$VenvDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
  }
  Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
  if (Test-Path $VenvDir) {
    Write-Warning "Failed to remove venv folder. It may be in use. Close any Python/uvicorn processes and retry."
    exit 1
  }
}
if (Test-Path $venvCfg) {
  $homeLine = Get-Content $venvCfg | Where-Object { $_ -match '^home = ' } | Select-Object -First 1
  if ($homeLine) {
    $venvHome = $homeLine -replace '^home = ', '' | ForEach-Object { $_.Trim() }
    if ($venvHome -notmatch '^[A-Za-z]:\\') {
      Write-Host "[!] Existing venv points to non-Windows python ($venvHome). Recreating..."
      Remove-Item -Recurse -Force $VenvDir
    }
  }
}
if (-not (Test-Path $VenvDir)) {
  $venvArgs = @('-m','venv', $VenvDir)
  & $PythonCmd.Cmd @($PythonCmd.Args + $venvArgs)
}
if (-not (Test-Path $venvCfg)) {
  Write-Error "pyvenv.cfg not found after venv creation at $VenvDir. Please re-run setup."
  exit 1
}

$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
  Write-Error "Venv python not found at $VenvPy"
  exit 1
}

Write-Host "[+] Installing router requirements"
& $VenvPy -m pip install --upgrade pip
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

if (Get-Process caddy -ErrorAction SilentlyContinue) {
  Write-Host "[+] Caddy is already running; skipping install/start checks." -ForegroundColor Green
}
$hasCaddy = $false
if (Get-Command caddy -ErrorAction SilentlyContinue) { $hasCaddy = $true }
if (-not $hasCaddy) {
  if (-not $InstallCaddy) {
    $answer = Read-Host "Caddy is not on PATH. Install it now? [Y/n]"
    if ($answer -and $answer -notmatch '^[Yy]$') {
      $InstallCaddy = $false
    } else {
      $InstallCaddy = $true
    }
  }
}

$caddyRunning = Get-Process caddy -ErrorAction SilentlyContinue
if ($caddyRunning) {
  Write-Host "[+] Caddy is already running; skipping install prompts." -ForegroundColor Green
}

if ($InstallCaddy -and -not $caddyRunning) {
  if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
      Write-Host "[+] Installing Caddy via winget" -ForegroundColor Yellow
      winget install -e --id Caddy.Caddy
      if ($LASTEXITCODE -ne 0) {
        winget install -e --id CaddyServer.Caddy
      }
    } elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
      Write-Host "[+] Installing Caddy via scoop" -ForegroundColor Yellow
      scoop install caddy
    } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
      Write-Host "[+] Installing Caddy via choco" -ForegroundColor Yellow
      choco install caddy -y
    } else {
      Write-Warning "No package manager found. Install Caddy manually: https://caddyserver.com/docs/install"
    }
  }
  if (-not (Get-Command caddy -ErrorAction SilentlyContinue)) {
    $caddyPath = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\CaddyServer.Caddy*\\caddy.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($caddyPath) {
      Write-Host "Caddy installed at: $($caddyPath.FullName)"
      Write-Host "Restart your shell or run it directly:"
      Write-Host "& `"$($caddyPath.FullName)`" run --config `"$CaddyFile`""
    }
  }
}

# Check port 80 usage (WSL relay commonly holds it)
if (-not $caddyRunning) {
  $port80 = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($port80) {
    $proc = Get-Process -Id $port80.OwningProcess -ErrorAction SilentlyContinue
    $procName = if ($proc) { $proc.ProcessName } else { 'unknown' }
    if ($procName -ne 'caddy') {
      Write-Host "Port 80 is in use by $procName (pid $($port80.OwningProcess))." -ForegroundColor Yellow
      if ($procName -eq 'wslrelay' -and (Get-Command wsl -ErrorAction SilentlyContinue)) {
        $shutdown = Read-Host "Shutdown WSL now to free port 80? [Y/n]"
        if (-not $shutdown -or $shutdown -match '^[Yy]$') {
          wsl --shutdown | Out-Null
          Write-Host "WSL shut down. You can now start Caddy." -ForegroundColor Green
        }
      }
    }
  }
}

if ($InstallShim) {
  $Shim = Join-Path $RepoDir "devhost.ps1"
  if (-not (Test-Path $Shim)) {
    Write-Warning "devhost.ps1 shim not found in repo."
  }
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1) Preferred: start both Caddy + router in the background:" -ForegroundColor Yellow
Write-Host "   .\\devhost.ps1 start" -ForegroundColor Green
Write-Host "   (This avoids a blocked terminal.)" -ForegroundColor DarkGreen
Write-Host "2) Manual (if you prefer separate commands):" -ForegroundColor Yellow
Write-Host "   Start Caddy (background):" -ForegroundColor Yellow
$caddyExe = (Get-Command caddy -ErrorAction SilentlyContinue).Source
if (-not $caddyExe) {
  $caddyExe = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\CaddyServer.Caddy*\\caddy.exe" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if ($caddyExe) {
  Write-Host "   & `"$caddyExe`" start --config `"$CaddyFile`"" -ForegroundColor Green
  Write-Host "   (Use 'run' instead of 'start' if you want foreground logs.)" -ForegroundColor DarkGreen
} else {
  Write-Host "   caddy start --config $CaddyFile" -ForegroundColor Green
}
Write-Host "   Start the router (run from repo root):" -ForegroundColor Yellow
Write-Host "   cd `"$RepoDir\\router`"" -ForegroundColor Green
Write-Host "   $VenvPy -m uvicorn app:app --host 127.0.0.1 --port 5555 --reload" -ForegroundColor Green
Write-Host "3) Use the CLI (PowerShell):" -ForegroundColor Yellow
Write-Host "   .\\devhost.ps1 add <name> <port>" -ForegroundColor Green
Write-Host "   .\\devhost.ps1 open <name>" -ForegroundColor Green
Write-Host "   (The router requires a Host header; don't browse http://127.0.0.1:5555 directly.)" -ForegroundColor DarkGreen
Write-Host "4) Use the CLI (Git Bash):" -ForegroundColor Yellow
Write-Host "   ./devhost add <name> <port>" -ForegroundColor Green
Write-Host ""
