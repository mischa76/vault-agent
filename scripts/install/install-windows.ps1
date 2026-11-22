<#
.SYNOPSIS
    Vault-Agent one-shot installer for Windows 11 (WSL2 + Ubuntu).

.DESCRIPTION
    Stage 1 (this script, elevated PowerShell):
      - checks/installs WSL2 with Ubuntu (may require ONE reboot)
      - after Ubuntu exists, runs scripts/install/setup-wsl.sh inside it

    Stage 2 (setup-wsl.sh, inside Ubuntu):
      - apt packages (git, curl, PostgreSQL 16)
      - uv (Python toolchain), clone of vault-agent onto ext4 (~/vault-agent)
      - uv sync (incl. demo extra), Postgres role/db 'vault', .env from template
      - keyless smoke test (pytest)

    The script is idempotent: re-run it after a reboot or after Ubuntu's
    first-launch username setup and it continues where it left off.

.USAGE
    Right-click PowerShell -> "Run as administrator", then:
      Set-ExecutionPolicy -Scope Process Bypass -Force
      .\install-windows.ps1

.NOTES
    - Requires internet access (apt, GitHub, astral.sh, dbt hub).
    - An Anthropic API key is optional at install time; without it the test
      suite and both Postgres demos still work (they are keyless by design).
#>
[CmdletBinding()]
param(
    [string]$Distro   = "Ubuntu",
    [string]$SetupUrl = "https://raw.githubusercontent.com/mischa76/vault-agent/main/scripts/install/setup-wsl.sh",
    # Skip the WSL/Ubuntu installation check (jump straight to stage 2)
    [switch]$SkipWslInstall
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# --- 0. Elevation check -------------------------------------------------------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this script in an ADMINISTRATOR PowerShell (installing WSL requires admin rights)." -ForegroundColor Red
    exit 1
}

# --- 1. WSL + Ubuntu ----------------------------------------------------------
if (-not $SkipWslInstall) {
    Write-Step "Checking WSL/Ubuntu"

    # wsl.exe prints UTF-16; strip NULs so string matching works.
    $installed = @()
    try {
        $installed = (& wsl.exe --list --quiet 2>$null) -replace "`0", "" |
                     Where-Object { $_ -and $_.Trim() }
    } catch { $installed = @() }

    $hasDistro = $installed | Where-Object { $_ -match "^$Distro" }

    if (-not $hasDistro) {
        Write-Step "Installing WSL2 + $Distro (one-time; takes a few minutes)"
        & wsl.exe --install -d $Distro
        Write-Host @"

--------------------------------------------------------------------------
 NEXT STEPS (one-time):
 1. If Windows asks for a RESTART: reboot now.
 2. Ubuntu then starts automatically (or open 'Ubuntu' from the Start menu)
    and asks ONCE for a Linux username + password.
    You will need that password later for 'sudo' - remember it!
 3. Then run this script AGAIN - it will continue with the actual
    Vault-Agent installation.
--------------------------------------------------------------------------
"@ -ForegroundColor Yellow
        exit 0
    }

    Write-Host "WSL/$Distro is present." -ForegroundColor Green

    # Distro registered but never initialized? (no default user -> root)
    $whoami = (((& wsl.exe -d $Distro -- whoami 2>$null) -replace "`0", "") | Out-String).Trim()
    if (-not $whoami) {
        Write-Host "Ubuntu is installed but not initialized yet. Please open 'Ubuntu' from the Start menu, create your user, then run this script again." -ForegroundColor Yellow
        exit 0
    }
    if ($whoami -eq "root") {
        Write-Host "Note: Ubuntu runs as root (no default user created). The installation works, but a regular user would be cleaner (open 'Ubuntu' from the Start menu)." -ForegroundColor Yellow
    }
}

# --- 2. Stage 2 inside Ubuntu ---------------------------------------------------
Write-Step "Running setup inside $Distro"

$localSetup = Join-Path $PSScriptRoot "setup-wsl.sh"
if (Test-Path $localSetup) {
    # Use the setup-wsl.sh lying next to this script (strip CRLF for bash).
    $winPath = (Resolve-Path $localSetup).Path
    $wslPath = (((& wsl.exe -d $Distro -- wslpath -a "$winPath") -replace "`0", "") | Out-String).Trim()
    & wsl.exe -d $Distro --cd ~ -- bash -c "tr -d '\r' < '$wslPath' > /tmp/vault-agent-setup.sh && bash /tmp/vault-agent-setup.sh"
} else {
    # Fallback: fetch stage 2 straight from GitHub.
    & wsl.exe -d $Distro --cd ~ -- bash -c "curl -fsSL '$SetupUrl' | tr -d '\r' > /tmp/vault-agent-setup.sh && bash /tmp/vault-agent-setup.sh"
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSetup inside $Distro finished with an error (exit $LASTEXITCODE). Check the output above; the script is safe to re-run." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Step "Done"
Write-Host @"
Vault-Agent is installed. Getting started (in an Ubuntu terminal):

  cd ~/vault-agent
  uv run pytest -q                # test suite, runs WITHOUT an API key
  cd demo/bank_postgres           # runnable demo, WITHOUT an API key
  # with an API key (.env):
  uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output

Details: README.md in the repo and scripts/install/README.md
"@ -ForegroundColor Green
