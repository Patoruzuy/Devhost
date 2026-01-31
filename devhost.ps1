param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ArgsList
)

$Elevated = $false
if ($ArgsList -contains '--elevated') {
  $Elevated = $true
  $ArgsList = $ArgsList | Where-Object { $_ -ne '--elevated' }
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Config = Join-Path $Root 'devhost.json'
$CaddyFile = Join-Path $Root 'caddy\Caddyfile'
$DomainFile = Join-Path $Root '.devhost\domain'
$RouterDir = Join-Path $Root 'router'
$PidFile = Join-Path $Root '.devhost\router.pid'
$LogFile = Join-Path $env:TEMP 'devhost-router.log'
$ErrFile = Join-Path $env:TEMP 'devhost-router.err.log'

function Test-Admin {
  $current = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($current)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-HostsPath {
  return Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
}

function Add-HostsEntry($hostname) {
  if (-not $hostname) { return }
  $hostsPath = Get-HostsPath
  if (-not (Test-Path $hostsPath)) { return }
  if (-not (Test-Admin)) {
    Write-Host "DNS: hosts update skipped (not running as Administrator)."
    Write-Host "Hint: run PowerShell as Administrator to add $hostname to hosts."
    return
  }
  $content = Get-Content $hostsPath -Raw
  if ($content -match "(?m)^\s*127\.0\.0\.1\s+$([regex]::Escape($hostname))(\s|$)") {
    return
  }
  $line = "127.0.0.1 $hostname # devhost"
  Add-Content -Path $hostsPath -Encoding ascii -Value "`r`n$line"
}

function Remove-HostsEntry($hostname) {
  if (-not $hostname) { return }
  $hostsPath = Get-HostsPath
  if (-not (Test-Path $hostsPath)) { return }
  if (-not (Test-Admin)) { return }
  $lines = Get-Content $hostsPath
  $filtered = $lines | Where-Object { $_ -notmatch "\b$([regex]::Escape($hostname))\b" -or $_ -notmatch "devhost" }
  Set-Content -Path $hostsPath -Encoding ascii -Value $filtered
}

function Sync-Hosts {
  $domain = Get-Domain
  if ($domain -eq 'localhost') { return }
  $cfg = Get-Config
  foreach ($p in $cfg.PSObject.Properties) {
    Add-HostsEntry "$($p.Name).$domain"
  }
}

function Invoke-Hosts($argsList) {
  $sub = if ($argsList.Count -gt 1) { $argsList[1] } else { '' }
  if ($sub -eq 'sync') {
    if (-not (Test-Admin)) {
      Write-Host "Hosts sync requires Administrator privileges."
      return
    }
    Sync-Hosts
    Write-Host "Hosts entries synced."
    return
  }
  if ($sub -eq 'clear') {
    if (-not (Test-Admin)) {
      Write-Host "Hosts clear requires Administrator privileges."
      return
    }
    $hostsPath = Get-HostsPath
    if (-not (Test-Path $hostsPath)) { Write-Host "Hosts file not found."; return }
    $lines = Get-Content $hostsPath
    $filtered = $lines | Where-Object { $_ -notmatch "# devhost" }
    Set-Content -Path $hostsPath -Encoding ascii -Value $filtered
    Write-Host "Hosts entries cleared."
    return
  }
  Write-Host "Usage: devhost hosts sync|clear"
}

function Start-ElevationIfNeeded($argsList) {
  if ($Elevated) { return }
  if (Test-Admin) { return }
  if (-not $argsList -or $argsList.Count -eq 0) { return }

  $command = $argsList[0]
  $domain = Get-Domain
  if ($command -eq 'domain' -and $argsList.Count -gt 1) {
    $domain = $argsList[1]
  }
  if ($domain -eq 'localhost') { return }

  if ($command -in @('add','remove','hosts')) {
    Write-Host "Re-launching as Administrator to update hosts entries..."
    $elevateArgs = @('-NoProfile','-ExecutionPolicy','Bypass','-File', $PSCommandPath, '--elevated') + $argsList
    Start-Process powershell -ArgumentList $elevateArgs -Verb RunAs
    exit
  }
}

function Validate-Name($name) {
  if (-not $name) { Write-Host "Name is required."; return $false }
  if ($name.Length -gt 63) { Write-Host "Name too long (max 63 chars)."; return $false }
  if ($name -notmatch '^[A-Za-z0-9-]+$') {
    Write-Host "Invalid name. Use only letters, numbers, and hyphens."
    return $false
  }
  return $true
}

function Validate-Port($port) {
  if ($port -notmatch '^\d+$') { return $false }
  $p = [int]$port
  return ($p -ge 1 -and $p -le 65535)
}

function Validate-Target($target) {
  if (-not $target) { Write-Host "Port must be a number or host:port"; return $false }
  if ($target -match '^https?://') {
    try {
      $uri = [uri]$target
      if (-not $uri.Host) { Write-Host "Target must include a host."; return $false }
      if (-not (Validate-Port $uri.Port)) { Write-Host "Port must be 1-65535."; return $false }
      return $true
    } catch {
      Write-Host "Invalid URL target."
      return $false
    }
  }
  if ($target -match '^\d+$') {
    if (-not (Validate-Port $target)) { Write-Host "Port must be 1-65535."; return $false }
    return $true
  }
  if ($target -match '^[^:]+:\d+$') {
    $parts = $target.Split(':',2)
    if (-not (Validate-Port $parts[1])) { Write-Host "Port must be 1-65535."; return $false }
    return $true
  }
  Write-Host "Port must be a number or host:port"
  return $false
}

function Show-Usage {
  @'
Usage: devhost <command> [args]

Commands:
  add <name> <port|host:port>       Add a mapping
  add <name> --http <port|host:port>   Force http for dev URL (default)
  add <name> --https <port|host:port>  Force https for dev URL
  remove <name>                    Remove a mapping
  list                             List mappings
  list --json                      List mappings as JSON
  url [name]                       Print URL
  open [name]                      Open URL in default browser
  validate                         Quick config/router/DNS checks
  export caddy                     Print generated Caddyfile
  edit                             Open devhost.json in editor
  resolve <name>                   Show DNS resolution and port reachability
  doctor [--windows]               Deeper diagnostics
  doctor --windows --fix           Attempt Windows fixes (hosts sync + free port 80)
  info                             Show this help
  domain [name]                    Show or set base domain (default: localhost)
  hosts sync                       Re-apply hosts entries for all mappings (admin)
  hosts clear                      Remove all devhost entries from hosts (admin)
  caddy start|stop|restart|status  Manage Caddy on Windows
  start|stop|status                Manage router process (start also checks Caddy)
  install --windows                Run Windows installer
'@ | Write-Host
}

function Get-Config {
  if (-not (Test-Path $Config)) {
    '{}' | Set-Content -Encoding utf8 $Config
  }
  try {
    $raw = Get-Content $Config -Raw
    if (-not $raw.Trim()) { $raw = '{}' }
    return $raw | ConvertFrom-Json
  } catch {
    return @{}
  }
}

function Find-CaddyExe {
  $cmd = Get-Command caddy -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $caddyPath = Get-ChildItem "$env:LOCALAPPDATA\\Microsoft\\WinGet\\Packages\\CaddyServer.Caddy*\\caddy.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($caddyPath) { return $caddyPath.FullName }
  return $null
}

function Start-Caddy {
  $exe = Find-CaddyExe
  if (-not $exe) {
    Write-Host 'Caddy not found. Install with: .\scripts\setup-windows.ps1 -InstallCaddy'
    return
  }
  $existing = Get-Process caddy -ErrorAction SilentlyContinue
  if ($existing) {
    Write-Host 'Caddy already running'
    return
  }
  $listener = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($listener) {
    $pidValue = $listener.OwningProcess
    $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
    Write-Host "Port 80 is already in use by $name (pid $pidValue)." -ForegroundColor Red
    if ($name -eq 'wslrelay') {
      Write-Host "Hint: run 'wsl --shutdown' to free port 80." -ForegroundColor Yellow
    }
    Write-Host "Stop that process or free port 80, then retry." -ForegroundColor Yellow
    return
  }
  Start-Process -FilePath $exe -ArgumentList @('run','--config', $CaddyFile) -WorkingDirectory $Root | Out-Null
  Write-Host "Caddy starting with config: $CaddyFile"
}

function Save-Config($obj) {
  $json = $obj | ConvertTo-Json -Depth 20
  $tmp = Join-Path (Split-Path $Config) ([System.IO.Path]::GetRandomFileName())
  $json | Set-Content -Encoding utf8 $tmp
  Move-Item -Force $tmp $Config
}

function Get-FirstName {
  $cfg = Get-Config
  $keys = @($cfg.PSObject.Properties.Name | Sort-Object)
  if ($keys.Count -gt 0) { return $keys[0] }
  return $null
}

function Get-Domain {
  if ($env:DEVHOST_DOMAIN) { return $env:DEVHOST_DOMAIN.Trim() }
  if (Test-Path $DomainFile) {
    $val = Get-Content $DomainFile -Raw
    if ($val) { return $val.Trim() }
  }
  return 'localhost'
}

function Set-Domain($name) {
  if (-not $name) { Write-Host 'Usage: devhost domain <base-domain>'; return }
  if ($name -match 'https?://|/') { Write-Host 'Domain must be a host name only (no scheme or path).'; return }
  $dir = Split-Path $DomainFile
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $name | Set-Content -Encoding utf8 $DomainFile
  Write-Host "Domain set to $name"
  New-CaddyFile (Get-Config)
  if (Test-Admin) {
    Sync-Hosts
  } elseif ($name -ne 'localhost') {
    Write-Host "Run PowerShell as Administrator to update hosts entries for existing mappings."
  }
}

function Convert-Target($value) {
  if ($null -eq $value) { return $null }
  $scheme = 'http'
  $targetHost = '127.0.0.1'
  $port = $null
  $rest = $value.ToString()

  if ($rest -match '^https?://') {
    $scheme = $rest.Split('://')[0]
    $rest = $rest.Substring($scheme.Length + 3)
    $rest = $rest.Split('/')[0]
  }

  if ($rest -match ':') {
    $parts = $rest.Split(':',2)
    $targetHost = $parts[0]
    $port = $parts[1]
  } else {
    $port = $rest
  }

  if (-not $targetHost -or -not $port) { return $null }
  return @{ scheme=$scheme; host=$targetHost; port=$port }
}

function New-CaddyFile($cfg) {
  $domain = Get-Domain
  $lines = @(
    '# Autogenerated Caddyfile',
    "*.$domain {",
    '    reverse_proxy localhost:5555',
    '    tls internal',
    '}',
    ''
  )

  if ($cfg.PSObject.Properties.Count -gt 0) {
    $lines += '# Direct mappings'
    foreach ($p in $cfg.PSObject.Properties) {
      $name = $p.Name
      $value = $p.Value.ToString()
      $target = $value
      if ($value -notmatch '^https?://') {
        if ($value -notmatch ':') {
          $target = "127.0.0.1:$value"
        }
      }
      if ($value -match '^https://') {
        $lines += "$name.$domain {"
      } else {
        $lines += "http://$name.$domain {"
      }
      $lines += "    reverse_proxy $target"
      if ($value -match '^https://') {
        $lines += '    tls internal'
      }
      $lines += '}'
      $lines += ''
    }
  }

  $lines -join "`n" | Set-Content -Encoding utf8 $CaddyFile
}

function Add-Mapping($argsList) {
  if ($argsList.Count -lt 2) { Show-Usage; return }
  $name = $argsList[0]
  if (-not (Validate-Name $name)) { return }
  $scheme = $null
  $target = $null
  for ($i=1; $i -lt $argsList.Count; $i++) {
    switch ($argsList[$i]) {
      '--http' { $scheme = 'http' }
      '--https' { $scheme = 'https' }
      default { $target = $argsList[$i] }
    }
  }
  if (-not (Validate-Target $target)) { return }
  if ($scheme) {
    if ($target -match '^https?://') { Write-Host 'Target already includes a scheme'; return }
    if ($target -match '^\d+$') { $target = "127.0.0.1:$target" }
    $target = "${scheme}://$target"
  }
  if (-not $scheme -and $target -match '^\d+$') {
    $target = [int]$target
  }
  $cfg = Get-Config
  $cfg | Add-Member -NotePropertyName $name -NotePropertyValue $target -Force
  Save-Config $cfg
  New-CaddyFile $cfg
  $domain = Get-Domain
  if ($domain -ne 'localhost') { Add-HostsEntry "$name.$domain" }
  Write-Host "[+] Mapped $name.$domain to $target"
}

function Remove-Mapping($name) {
  if (-not $name) { Show-Usage; return }
  $cfg = Get-Config
  $cfg.PSObject.Properties.Remove($name) | Out-Null
  Save-Config $cfg
  New-CaddyFile $cfg
  $domain = Get-Domain
  if ($domain -ne 'localhost') { Remove-HostsEntry "$name.$domain" }
  Write-Host "[-] Removed mapping for $name.$domain"
}

function Get-Mappings([switch]$Json) {
  $cfg = Get-Config
  if ($Json) {
    $cfg | ConvertTo-Json -Depth 10
    return
  }
  $domain = Get-Domain
  if ($cfg.PSObject.Properties.Count -eq 0) {
    Write-Host 'No mappings yet. Add one with: devhost add <name> <port>'
    return
  }
  foreach ($p in ($cfg.PSObject.Properties | Sort-Object Name)) {
    $value = $p.Value.ToString()
    if ($value -match '^\d+$') { $value = "127.0.0.1:$value" }
    Write-Host "$($p.Name).$domain -> $value"
  }
}

function Get-UrlForName($name) {
  if (-not $name) { $name = Get-FirstName }
  if (-not $name) { Write-Host 'No mappings found.'; return $null }
  $cfg = Get-Config
  $value = $cfg.$name
  $domain = Get-Domain
  if (-not $value) { Write-Host "No mapping found for $name.$domain"; return $null }
  if ($value -match '^https://') { $scheme = 'https' } elseif ($value -match '^http://') { $scheme = 'http' } else { $scheme = 'http' }
  return "${scheme}://$name.$domain"
}

function Open-Url($name) {
  $url = Get-UrlForName $name
  if ($url) { Start-Process $url }
}

function Validate {
  Write-Host "Config: $Config"
  try { $null = Get-Config; Write-Host 'Config JSON: OK' } catch { Write-Host 'Config JSON: invalid' }

  try {
    $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:5555/health' -UseBasicParsing -TimeoutSec 2
    if ($resp.StatusCode -eq 200) { Write-Host 'Router: OK' } else { Write-Host 'Router: not responding' }
  } catch { Write-Host 'Router: not responding' }
}

function Resolve-Name($name) {
  if (-not $name) { Show-Usage; return }
  $cfg = Get-Config
  $value = $cfg.$name
  $domain = Get-Domain
  if (-not $value) { Write-Host "No mapping found for $name.$domain"; return }
  $norm = Convert-Target $value
  Write-Host "$name.$domain -> $($norm.scheme)://$($norm.host):$($norm.port)"

  try {
    $dns = Resolve-DnsName "$name.$domain" -ErrorAction Stop | Select-Object -First 1
    Write-Host "DNS: $($dns.IPAddress)"
  } catch {
    Write-Host 'DNS: unresolved'
  }

  $tnc = Test-NetConnection -ComputerName $norm.host -Port $norm.port -WarningAction SilentlyContinue
  if ($tnc.TcpTestSucceeded) { Write-Host "Port: $($norm.host):$($norm.port) is open" } else { Write-Host "Port: $($norm.host):$($norm.port) is not reachable" }
}

function Doctor {
  Write-Host "Devhost doctor"
  Validate
  $caddyExe = Find-CaddyExe
  $p = Get-Process caddy -ErrorAction SilentlyContinue
  if ($p) {
    Write-Host "Caddy: running (pid $($p.Id))"
  } elseif ($caddyExe) {
    Write-Host "Caddy: installed but not running"
    Write-Host "Start: & `"$caddyExe`" start --config `"$CaddyFile`""
  } else {
    Write-Host 'Caddy: not found'
    Write-Host 'Install: .\scripts\setup-windows.ps1 -InstallCaddy'
  }
  $domain = Get-Domain
  if ($domain -ne 'localhost') {
    try {
      $null = Resolve-DnsName "hello.$domain" -ErrorAction Stop | Select-Object -First 1
    } catch {
      Write-Host "DNS: $domain is not resolving on Windows."
      Write-Host "Hint: add an entry to the Windows hosts file (admin) or use a local DNS resolver (e.g. Acrylic)."
      Write-Host "Example hosts entry: 127.0.0.1 hello.$domain"
    }
  }
}

function Doctor-Windows {
  Write-Host "Devhost doctor (Windows)"
  $caddy = Get-Process caddy -ErrorAction SilentlyContinue
  $caddyExe = Find-CaddyExe
  if ($caddy) {
    Write-Host "Caddy: running (pid $($caddy.Id))"
  } elseif ($caddyExe) {
    Write-Host "Caddy: installed but not running"
    Write-Host "Start: & `"$caddyExe`" start --config `"$CaddyFile`""
  } else {
    Write-Host "Caddy: not found"
  }
  $port80 = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($port80) {
    $proc = Get-Process -Id $port80.OwningProcess -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
    Write-Host "Port 80: in use by $name (pid $($port80.OwningProcess))"
  } else {
    Write-Host "Port 80: free"
  }
  try {
    $null = Invoke-WebRequest -Uri 'http://127.0.0.1:5555/health' -UseBasicParsing -TimeoutSec 2
    Write-Host "Router: OK"
  } catch {
    Write-Host "Router: not responding"
  }
  $domain = Get-Domain
  if ($domain -ne 'localhost') {
    $hostsPath = Get-HostsPath
    if (Test-Path $hostsPath) {
      $missing = @()
      $cfg = Get-Config
      foreach ($p in $cfg.PSObject.Properties) {
        $entry = "$($p.Name).$domain"
        $content = Get-Content $hostsPath -Raw
        if ($content -notmatch "(?m)^\s*127\.0\.0\.1\s+$([regex]::Escape($entry))(\s|$)") {
          $missing += $entry
        }
      }
      if ($missing.Count -gt 0) {
        Write-Host "Hosts: missing entries for $($missing -join ', ')"
      } else {
        Write-Host "Hosts: OK"
      }
    }
  }
}

function Doctor-Windows-Fix {
  Write-Host "Devhost doctor (Windows) --fix"
  if (-not (Test-Admin)) {
    Write-Host "Fix requires Administrator privileges."
    return
  }
  $domain = Get-Domain
  if ($domain -ne 'localhost') {
    Sync-Hosts
    Write-Host "Hosts: synced"
  }
  $port80 = Get-NetTCPConnection -LocalPort 80 -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($port80) {
    $proc = Get-Process -Id $port80.OwningProcess -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
    if ($name -eq 'wslrelay' -and (Get-Command wsl -ErrorAction SilentlyContinue)) {
      Write-Host "Port 80 is held by wslrelay; shutting down WSL..."
      wsl --shutdown | Out-Null
      Write-Host "WSL shut down."
    }
  }
  $caddyExe = Find-CaddyExe
  if ($caddyExe) {
    Start-Process -FilePath $caddyExe -ArgumentList @('start','--config', $CaddyFile) -WorkingDirectory $Root | Out-Null
    Write-Host "Caddy: start requested"
  } else {
    Write-Host "Caddy not found; run scripts/setup-windows.ps1 -InstallCaddy"
  }
}

function Caddy-Command($argsList) {
  $sub = if ($argsList.Count -gt 1) { $argsList[1] } else { '' }
  $exe = Find-CaddyExe
  if (-not $exe) {
    Write-Host "Caddy not found. Install with: .\\scripts\\setup-windows.ps1 -InstallCaddy"
    return
  }
  switch ($sub) {
    'start' {
      Start-Process -FilePath $exe -ArgumentList @('start','--config', $CaddyFile) -WorkingDirectory $Root | Out-Null
      Write-Host "Caddy start requested"
    }
    'stop' {
      Start-Process -FilePath $exe -ArgumentList @('stop') -WorkingDirectory $Root | Out-Null
      Write-Host "Caddy stop requested"
    }
    'restart' {
      Start-Process -FilePath $exe -ArgumentList @('stop') -WorkingDirectory $Root | Out-Null
      Start-Sleep -Seconds 1
      Start-Process -FilePath $exe -ArgumentList @('start','--config', $CaddyFile) -WorkingDirectory $Root | Out-Null
      Write-Host "Caddy restart requested"
    }
    'status' {
      $running = Get-Process caddy -ErrorAction SilentlyContinue
      if ($running) { Write-Host "Caddy: running (pid $($running.Id))" } else { Write-Host "Caddy: not running" }
    }
    default {
      Write-Host "Usage: devhost caddy <start|stop|restart|status>"
    }
  }
}

function Start-Router {
  if (-not (Test-Path $RouterDir)) { Write-Host 'Router directory not found'; return }
  $venvPy = Join-Path $RouterDir 'venv\Scripts\python.exe'
  if (-not (Test-Path $venvPy)) { Write-Host 'Venv python not found. Run scripts\setup-windows.ps1'; return }
  $venvCfg = Join-Path $RouterDir 'venv\pyvenv.cfg'
  if (Test-Path $venvCfg) {
    $homeLine = Get-Content $venvCfg | Where-Object { $_ -match '^home = ' } | Select-Object -First 1
    if ($homeLine) {
      $venvHome = $homeLine -replace '^home = ', '' | ForEach-Object { $_.Trim() }
      if ($venvHome -notmatch '^[A-Za-z]:\\') {
        Write-Host "Venv appears to be created by WSL ($venvHome)."
        Write-Host "Delete router\\venv and rerun: .\\scripts\\setup-windows.ps1"
        return
      }
    }
  }
  New-Item -ItemType Directory -Force (Split-Path $PidFile) | Out-Null
  $uvicornArgs = '-m uvicorn app:app --host 127.0.0.1 --port 5555'
  $proc = Start-Process -FilePath $venvPy -ArgumentList $uvicornArgs -WorkingDirectory $RouterDir -PassThru -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile
  $proc.Id | Set-Content $PidFile
  Write-Host "Router started (pid $($proc.Id)), logs: $LogFile"
  Write-Host "Router errors: $ErrFile"
}

function Start-All {
  Start-Caddy
  Start-Router
}

function Stop-Router {
  if (-not (Test-Path $PidFile)) { Write-Host 'Router not running'; return }
  $pidValue = Get-Content $PidFile
  if ($pidValue) {
    try { Stop-Process -Id $pidValue -Force -ErrorAction Stop; Write-Host "Stopped $pidValue" } catch { Write-Host "Failed to stop $pidValue" }
  }
  Remove-Item $PidFile -ErrorAction SilentlyContinue
}

function Get-RouterStatus($json) {
  $running = $false
  $pidValue = $null
  if (Test-Path $PidFile) {
    $pidValue = Get-Content $PidFile
    if ($pidValue) {
      $p = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
      if ($p) { $running = $true }
    }
  }
  $health = 'unknown'
  try {
    $null = Invoke-WebRequest -Uri 'http://127.0.0.1:5555/health' -UseBasicParsing -TimeoutSec 2
    $health = 'ok'
  } catch {
    $health = 'not_responding'
  }
  if ($json) {
    $obj = @{ running=$running; pid=($pidValue -as [int]); health=$health }
    $obj | ConvertTo-Json -Compress
  } else {
    if ($running) { Write-Host "Router running (pid $pidValue)" } else { Write-Host 'Router not running' }
    Write-Host "Health check: $health"
  }
}

function Edit-Config {
  $editor = $env:EDITOR
  if (-not $editor) { $editor = 'notepad.exe' }
  Start-Process $editor $Config
}

Start-ElevationIfNeeded $ArgsList

switch ($ArgsList[0]) {
  'add' { Add-Mapping $ArgsList[1..($ArgsList.Count-1)] }
  'remove' { Remove-Mapping $ArgsList[1] }
  'list' { $json = $false; if ($ArgsList[1] -eq '--json') { $json = $true }; Get-Mappings -Json:$json }
  'url' { $u = Get-UrlForName $ArgsList[1]; if ($u) { Write-Host $u } }
  'open' { Open-Url $ArgsList[1] }
  'validate' { Validate }
  'export' { if ($ArgsList[1] -eq 'caddy') { Get-Content $CaddyFile } else { Show-Usage } }
  'edit' { Edit-Config }
  'resolve' { Resolve-Name $ArgsList[1] }
  'doctor' {
    if ($ArgsList[1] -eq '--windows' -and $ArgsList[2] -eq '--fix') { Doctor-Windows-Fix }
    elseif ($ArgsList[1] -eq '--windows') { Doctor-Windows }
    else { Doctor }
  }
  'info' { Show-Usage }
  'hosts' { Invoke-Hosts $ArgsList }
  'caddy' { Caddy-Command $ArgsList }
  'domain' { if ($ArgsList[1]) { Set-Domain $ArgsList[1] } else { Write-Host (Get-Domain) } }
  'start' { Start-All }
  'stop' { Stop-Router }
  'status' { $json = $false; if ($ArgsList[1] -eq '--json') { $json = $true }; Get-RouterStatus $json }
  'install' { if ($ArgsList[1] -eq '--windows') { & "$Root\scripts\setup-windows.ps1" } else { Show-Usage } }
  default { Show-Usage }
}
