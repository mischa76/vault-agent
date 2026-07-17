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
    Write-Host "Bitte in einer ADMINISTRATOR-PowerShell ausfuehren (WSL-Installation braucht Adminrechte)." -ForegroundColor Red
    exit 1
}

# --- 1. WSL + Ubuntu ----------------------------------------------------------
if (-not $SkipWslInstall) {
    Write-Step "Pruefe WSL/Ubuntu"

    # wsl.exe prints UTF-16; strip NULs so string matching works.
    $installed = @()
    try {
        $installed = (& wsl.exe --list --quiet 2>$null) -replace "`0", "" |
                     Where-Object { $_ -and $_.Trim() }
    } catch { $installed = @() }

    $hasDistro = $installed | Where-Object { $_ -match "^$Distro" }

    if (-not $hasDistro) {
        Write-Step "Installiere WSL2 + $Distro (einmalig; dauert ein paar Minuten)"
        & wsl.exe --install -d $Distro
        Write-Host @"

--------------------------------------------------------------------------
 NAECHSTE SCHRITTE (einmalig):
 1. Falls Windows einen NEUSTART verlangt: neu starten.
 2. Ubuntu startet danach automatisch (oder 'Ubuntu' im Startmenue oeffnen)
    und fragt EINMALIG nach einem Linux-Benutzernamen + Passwort.
    Das Passwort brauchst du spaeter fuer 'sudo' - merken!
 3. Danach dieses Script ERNEUT ausfuehren - es macht dann mit der
    eigentlichen Vault-Agent-Installation weiter.
--------------------------------------------------------------------------
"@ -ForegroundColor Yellow
        exit 0
    }

    Write-Host "WSL/$Distro ist vorhanden." -ForegroundColor Green

    # Distro registered but never initialized? (no default user -> root)
    $whoami = (((& wsl.exe -d $Distro -- whoami 2>$null) -replace "`0", "") | Out-String).Trim()
    if (-not $whoami) {
        Write-Host "Ubuntu ist installiert, aber noch nicht initialisiert. Bitte 'Ubuntu' im Startmenue oeffnen, Benutzer anlegen, dann dieses Script erneut ausfuehren." -ForegroundColor Yellow
        exit 0
    }
    if ($whoami -eq "root") {
        Write-Host "Hinweis: Ubuntu laeuft als root (kein Standardbenutzer angelegt). Die Installation funktioniert, aber ein normaler Benutzer waere sauberer ('Ubuntu' im Startmenue oeffnen)." -ForegroundColor Yellow
    }
}

# --- 2. Stage 2 inside Ubuntu ---------------------------------------------------
Write-Step "Starte Setup innerhalb von $Distro"

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
    Write-Host "`nSetup in $Distro ist mit Fehler beendet (Exit $LASTEXITCODE). Ausgabe oben pruefen; das Script kann gefahrlos erneut ausgefuehrt werden." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Step "Fertig"
Write-Host @"
Vault-Agent ist installiert. Einstieg (im Ubuntu-Terminal):

  cd ~/vault-agent
  uv run pytest -q                # Testsuite, laeuft OHNE API-Key
  cd demo/bank_postgres           # lauffaehige Demo, OHNE API-Key
  # mit API-Key (.env):
  uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output

Details: README.md im Repo bzw. scripts/install/README.md
"@ -ForegroundColor Green
