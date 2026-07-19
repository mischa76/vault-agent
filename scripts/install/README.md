# Installing Vault-Agent on Windows 11 (WSL2)

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

## Troubleshooting

- **`uv: command not found` / `~/vault-agent: No such file or directory`** right after
  Ubuntu's very first launch: stage 2 has not run yet — you are in a fresh distro. Run
  the stage-2 one-liner above (or re-run `install-windows.ps1` in PowerShell; it
  continues where it left off). Do **not** follow Ubuntu's `snap install astral-uv`
  hint — snap is not the supported install path here.
