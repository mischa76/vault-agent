# Vault-Agent Installation auf Windows 11 (WSL2)

Zwei Stufen, ein Einstiegspunkt: `install-windows.ps1` installiert bei Bedarf
WSL2 + Ubuntu und ruft danach `setup-wsl.sh` innerhalb von Ubuntu auf, das den
Rest erledigt (Pakete, uv, Repo-Clone auf ext4, PostgreSQL, `.env`, Smoke-Test).

## Voraussetzungen

- Windows 11 mit aktivierter Virtualisierung (BIOS/UEFI; auf Firmen-Notebooks
  gelegentlich per Policy gesperrt — das ist der einzige typische Showstopper)
- Adminrechte + Internetzugang
- Optional: ein Anthropic API Key (ohne Key laufen Testsuite und beide
  Postgres-Demos trotzdem — die LLM-Pipeline braucht ihn)

## Ablauf

1. **PowerShell als Administrator** öffnen, dann:

   ```powershell
   # Script herunterladen (oder aus einem vorhandenen Checkout verwenden)
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
