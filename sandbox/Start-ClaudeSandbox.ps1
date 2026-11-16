<#
.SYNOPSIS
  Runs Claude Code inside a Microsoft Execution Containers (MXC) ProcessContainer
  on Windows 11 24H2+ with: project folder read/write, git + Git Bash + Node
  read-only, a private home/config dir per sandbox, and hostname-allowlisted
  network egress through a loopback proxy.

.EXAMPLE
  .\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo
  .\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo -Mode Learn   # deny + record what was blocked
  .\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo -Mode Audit   # allow + record (trusted runs only!)
  .\Start-ClaudeSandbox.ps1 -Workspace C:\src\my-repo -ClaudeArgs '-p','run the tests and fix failures'

.NOTES
  One-time setup in this folder:  npm install @microsoft/mxc-sdk
  (the npm package ships wxc-exec.exe under node_modules\@microsoft\mxc-sdk\bin\<arch>\)
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $Workspace,
  [string]   $Name = (Split-Path $Workspace -Leaf),
  [ValidateSet('Enforce', 'Learn', 'Audit')] [string] $Mode = 'Enforce',
  [int]      $ProxyPort = 18080,
  [string[]] $ClaudeArgs = @(),
  # Extra read-only tool folders, e.g. 'C:\Python313', 'C:\Program Files\dotnet'
  [string[]] $ExtraReadOnly = @(),
  # Pass ANTHROPIC_API_KEY from the host into the sandbox (otherwise run /login once inside)
  [switch]   $PassApiKey
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

# ---------- 1. Locate tools on the host ----------
$arch    = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'x64' }
$wxc     = Join-Path $here "node_modules\@microsoft\mxc-sdk\bin\$arch\wxc-exec.exe"
if (-not (Test-Path $wxc)) { throw "wxc-exec.exe not found. Run 'npm install @microsoft/mxc-sdk' in $here." }

$claude  = (Get-Command claude.exe -ErrorAction Stop).Source          # native installer: %USERPROFILE%\.local\bin\claude.exe
$gitRoot = Split-Path (Split-Path (Get-Command git.exe -ErrorAction Stop).Source)  # ...\Git
$bash    = Join-Path $gitRoot 'bin\bash.exe'                         # Claude Code on Windows needs Git Bash
$nodeDir = Split-Path (Get-Command node.exe -ErrorAction Stop).Source  # for npx-based MCP servers / plugins
$Workspace = (Resolve-Path $Workspace).Path

# ---------- 2. Private per-sandbox state (never the real user profile) ----------
$sbx      = Join-Path $env:LOCALAPPDATA "agent-sandboxes\$Name"
$home_    = Join-Path $sbx 'home'           # becomes USERPROFILE/HOME inside
$cfg      = Join-Path $home_ '.claude'      # CLAUDE_CONFIG_DIR: settings, plugins, MCP config, credentials
$tmp      = Join-Path $sbx 'tmp'
$npmCache = Join-Path $sbx 'npm-cache'
$npmPfx   = Join-Path $sbx 'npm-global'
$logs     = Join-Path $sbx 'logs'
foreach ($d in $home_, $cfg, $tmp, $npmCache, $npmPfx, $logs) { New-Item -ItemType Directory -Force $d | Out-Null }

# Sandbox-only git config: no credential helper, no host ~/.gitconfig includes.
# The agent can commit locally; pushing stays a human step on the host.
$gitcfg = Join-Path $sbx 'gitconfig'
@"
[user]
    name = Claude Code (sandboxed)
    email = claude-sandbox@invalid
[safe]
    directory = $($Workspace -replace '\\','/')
[credential]
    helper =
[core]
    autocrlf = true
"@ | Set-Content -Encoding utf8 $gitcfg

# ---------- 3. Start the allowlisting egress proxy (host side) ----------
$proxyLog = Join-Path $logs 'egress.jsonl'
$proxy = Start-Process -PassThru -WindowStyle Hidden -FilePath (Join-Path $nodeDir 'node.exe') `
  -ArgumentList @("`"$here\egress-proxy.mjs`"", $ProxyPort, "`"$here\allowlist.txt`"", "`"$proxyLog`"")
Start-Sleep -Milliseconds 700

try {
  # ---------- 4. Build the MXC policy ----------
  $envBlock = @(
    "SYSTEMROOT=$env:SystemRoot", "WINDIR=$env:windir", "COMSPEC=$env:ComSpec",
    "PATHEXT=$env:PATHEXT", "PROCESSOR_ARCHITECTURE=$env:PROCESSOR_ARCHITECTURE",
    "PATH=$(Split-Path $claude);$gitRoot\cmd;$gitRoot\usr\bin;$nodeDir;$npmPfx;$env:SystemRoot\System32;$env:SystemRoot",
    "USERPROFILE=$home_", "HOME=$home_",
    "LOCALAPPDATA=$home_\AppData\Local", "APPDATA=$home_\AppData\Roaming",   # PSEC may remap LOCALAPPDATA to the container profile
    "TEMP=$tmp", "TMP=$tmp",
    "CLAUDE_CONFIG_DIR=$cfg",
    "CLAUDE_CODE_GIT_BASH_PATH=$bash",
    "DISABLE_AUTOUPDATER=1",                       # update on the host, not from inside the box
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1",  # no telemetry/error-reporting endpoints needed
    "GIT_CONFIG_GLOBAL=$gitcfg", "GIT_CONFIG_NOSYSTEM=1", "GIT_TERMINAL_PROMPT=0",
    "npm_config_cache=$npmCache", "npm_config_prefix=$npmPfx"
  )
  if ($PassApiKey) {
    if (-not $env:ANTHROPIC_API_KEY) { throw '-PassApiKey given but ANTHROPIC_API_KEY is not set on the host.' }
    $envBlock += "ANTHROPIC_API_KEY=$env:ANTHROPIC_API_KEY"   # use a dedicated, revocable key per developer
  }

  $cmd = (@("`"$claude`"") + ($ClaudeArgs | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } })) -join ' '

  $policy = [ordered]@{
    '$schema'   = 'https://raw.githubusercontent.com/microsoft/mxc/main/schemas/stable/mxc-config.schema.1.0.0.json'
    version     = '1.0.0'
    containment = 'processcontainer'
    lifecycle   = @{ destroyOnExit = $true }
    process     = [ordered]@{
      commandLine = $cmd
      cwd         = $Workspace
      env         = $envBlock          # supplied verbatim: nothing from the host env leaks in
      timeout     = 0
    }
    filesystem  = [ordered]@{
      readwritePaths = @($Workspace, $sbx)
      readonlyPaths  = @(@(
        (Split-Path $claude),                                   # claude.exe
        (Join-Path $env:USERPROFILE '.local\share\claude'),     # native-install version store
        $gitRoot, $nodeDir
      ) + $ExtraReadOnly | Where-Object { Test-Path $_ })
      deniedPaths    = @(@(
        (Join-Path $Workspace '.env'),                          # belt and braces; keep secrets out of repos anyway
        (Join-Path $env:USERPROFILE '.ssh'),
        (Join-Path $env:USERPROFILE '.aws'),
        (Join-Path $env:USERPROFILE '.azure'),
        (Join-Path $env:USERPROFILE '.kube'),
        (Join-Path $env:USERPROFILE '.claude')                  # the host's own Claude config/hooks
      ) | Where-Object { Test-Path $_ })
    }
    network     = [ordered]@{
      egress  = @{ default = 'deny' }                           # no direct sockets at all
      ingress = @{ default = 'allow'; hostLoopback = 'allow' }  # required for an unpackaged host proxy (see README)
    }
    runtimeConfig = @{ networkProxy = "http://127.0.0.1:$ProxyPort" }  # MXC sets HTTP(S)_PROXY + WinHTTP proxy
    ui = [ordered]@{ disable = $true; clipboard = 'none'; injection = $false }
  }
  if ($Mode -eq 'Learn') {
    $policy.processContainer = @{ captureDenials = @{ mode = 'block'; outputPath = (Join-Path $logs 'denials.json') } }
  }

  $policyFile = Join-Path $sbx 'policy.json'
  $policy | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $policyFile

  # ---------- 5. Check the host can enforce it, then run ----------
  & $wxc --probe $policyFile | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "This host cannot enforce the policy (wxc-exec --probe failed). Windows 11 24H2 26100.9278+ required." }

  Write-Host "Sandbox '$Name'  mode=$Mode  workspace=$Workspace" -ForegroundColor Cyan
  Write-Host "  policy:  $policyFile`n  egress:  $proxyLog" -ForegroundColor DarkGray

  # Run from a real terminal: wxc-exec then shares the console with the child,
  # so Claude Code's interactive TUI works.
  if ($Mode -eq 'Audit') { & $wxc --audit $policyFile } else { & $wxc $policyFile }
  $exit = $LASTEXITCODE
}
finally {
  if ($proxy -and -not $proxy.HasExited) { Stop-Process -Id $proxy.Id -Force }
}

$denied = Get-Content $proxyLog -ErrorAction SilentlyContinue | ConvertFrom-Json | Where-Object decision -eq 'deny'
if ($denied) {
  Write-Host "`nBlocked egress this session:" -ForegroundColor Yellow
  $denied | Group-Object host, port | ForEach-Object { "  {0}  x{1}" -f $_.Name, $_.Count }
}
exit $exit
