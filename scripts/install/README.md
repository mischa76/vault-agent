# Installing Vault-Agent on Windows 11 (WSL2)

*Deutsche Fassung weiter unten.*

Two stages, one entry point: `install-windows.ps1` installs WSL2 + Ubuntu if
needed, then runs `setup-wsl.sh` inside Ubuntu, which does the rest (packages,
uv, repo clone onto ext4, PostgreSQL, `.env`, smoke test).

## Prerequisites

- Windows 11 with virtualization enabled (BIOS/UEFI; occasionally blocked by
  policy on corporate notebooks — the only typical showstopper)
- Admin rights + internet access
- Optional: an Anthropic API key (without one, the test suite and both
  Postgres demos still work — only the LLM pipeline needs it)

## Steps

1. Open **PowerShell as administrator**, then:

   ```powershell
   # Download the script (or use it from an existing checkout)
   irm https://raw.githubusercontent.com/mischa76/vault-agent/main/scripts/install/install-windows.ps1 -OutFile install-windows.ps1
   Set-ExecutionPolicy -Scope Process Bypass -Force
   .\install-windows.ps1
   ```

2. If WSL/Ubuntu was not installed yet: **reboot once**, create a **Linux
   user + password** on Ubuntu's first launch (that password is your later
   `sudo` password), then **run the script again**. It is idempotent and
   continues where it left off.

3. During setup, Ubuntu asks for your `sudo` password and optionally for the
   Anthropic API key (Enter = skip).

The repo lands in `~/vault-agent` **on the Linux filesystem (ext4)** —
deliberately not under `/mnt/c`, where git/Python I/O is painfully slow.

## Stage 2 only (existing WSL/Ubuntu or a native Linux machine)

```bash
curl -fsSL https://raw.githubusercontent.com/mischa76/vault-agent/main/scripts/install/setup-wsl.sh | bash
```

Configurable via environment variables: `VAULT_AGENT_DIR` (target directory,
default `~/vault-agent`), `VAULT_AGENT_REPO` (git URL).

## After installation

```bash
cd ~/vault-agent
uv run pytest -q                       # keyless
cd demo/bank_postgres                  # end-to-end demo, keyless
# with an API key in .env:
uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

Note without systemd: after a Windows reboot, run
`sudo service postgresql start` once (the setup prints whether this applies).

---

# Deutsch: Vault-Agent auf Windows 11 (WSL2) installieren

Zwei Stufen, ein Einstiegspunkt: `install-windows.ps1` installiert bei Bedarf
WSL2 + Ubuntu und ruft danach `setup-wsl.sh` innerhalb von Ubuntu auf, das den
Rest erledigt (Pakete, uv, Repo-Clone auf ext4, PostgreSQL, `.env`, Smoke-Test).

## Voraussetzungen

- Windows 11 mit aktivierter Virtualisierung (BIOS/UEFI; auf Firmen-Notebooks
  gelegentlich per Policy gesperrt — der einzige typische Showstopper)
- Adminrechte + Internetzugang
- Optional: ein Anthropic API Key (ohne Key laufen Testsuite und beide
  Postgres-Demos trotzdem — nur die LLM-Pipeline braucht ihn)

## Ablauf

1. **PowerShell als Administrator** öffnen, dann:

   ```powershell
   irm https://raw.githubusercontent.com/mischa76/vault-agent/main/scripts/install/install-windows.ps1 -OutFile install-windows.ps1
   Set-ExecutionPolicy -Scope Process Bypass -Force
   .\install-windows.ps1
   ```

2. War WSL/Ubuntu noch nicht installiert: **einmal neu starten**, im
   Ubuntu-Erststart **Linux-Benutzer + Passwort** anlegen (Passwort = späteres
   `sudo`-Passwort), dann das Script **erneut ausführen**. Es ist idempotent
   und macht dort weiter, wo es aufgehört hat.

3. Während des Setups fragt Ubuntu nach dem `sudo`-Passwort und optional nach
   dem Anthropic API Key (Enter = überspringen).

Das Repo landet unter `~/vault-agent` **im Linux-Dateisystem (ext4)** —
absichtlich nicht unter `/mnt/c`, dort ist Git/Python-I/O quälend langsam.

## Nur Stufe 2 (bereits vorhandenes WSL/Ubuntu oder nativer Linux-Rechner)

```bash
curl -fsSL https://raw.githubusercontent.com/mischa76/vault-agent/main/scripts/install/setup-wsl.sh | bash
```

Konfigurierbar per Umgebungsvariablen: `VAULT_AGENT_DIR` (Zielverzeichnis,
Default `~/vault-agent`), `VAULT_AGENT_REPO` (Git-URL).

## Nach der Installation

```bash
cd ~/vault-agent
uv run pytest -q                       # keyless
cd demo/bank_postgres                  # End-to-End-Demo, keyless
# mit API-Key in .env:
uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output
```

Hinweis ohne systemd: nach einem Windows-Neustart einmal
`sudo service postgresql start` ausführen (das Setup gibt aus, ob das nötig ist).
