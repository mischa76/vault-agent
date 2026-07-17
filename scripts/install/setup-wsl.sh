#!/usr/bin/env bash
# Vault-Agent stage-2 setup: runs INSIDE WSL Ubuntu (called by install-windows.ps1,
# but can also be run standalone on any Ubuntu 22.04+/Debian machine).
#
#   curl -fsSL https://raw.githubusercontent.com/mischa76/vault-agent/main/scripts/install/setup-wsl.sh | bash
#
# Idempotent: safe to re-run. Needs sudo (asks for your Linux password).
set -euo pipefail

REPO_URL="${VAULT_AGENT_REPO:-https://github.com/mischa76/vault-agent.git}"
TARGET_DIR="${VAULT_AGENT_DIR:-$HOME/vault-agent}"   # ext4! NOT /mnt/c - I/O there is painfully slow

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
note() { printf '\033[1;33m    %s\033[0m\n' "$*"; }

if [[ "$TARGET_DIR" == /mnt/* ]]; then
    note "WARNUNG: Zielverzeichnis liegt unter /mnt/* (Windows-Dateisystem) - das ist SEHR langsam."
    note "Empfohlen: VAULT_AGENT_DIR nicht setzen (Default: ~/vault-agent auf ext4)."
fi

# --- 1. System packages -------------------------------------------------------
step "[1/7] Systempakete (git, curl, PostgreSQL)"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates postgresql postgresql-contrib

# --- 2. uv ---------------------------------------------------------------------
step "[2/7] uv (Python-Toolchain)"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

# --- 3. Clone / update repo ----------------------------------------------------
step "[3/7] Repo -> $TARGET_DIR"
if [ -d "$TARGET_DIR/.git" ]; then
    git -C "$TARGET_DIR" pull --ff-only || note "git pull fehlgeschlagen (lokale Aenderungen?) - fahre mit vorhandenem Stand fort."
else
    git clone "$REPO_URL" "$TARGET_DIR"
fi
cd "$TARGET_DIR"

# --- 4. Python environment -----------------------------------------------------
step "[4/7] Python-Umgebung (uv sync, inkl. demo- und dev-Extras)"
uv sync --extra demo --extra dev

# --- 5. PostgreSQL: service + role/db 'vault' ----------------------------------
step "[5/7] PostgreSQL starten und Rolle/DB 'vault' anlegen"
sudo service postgresql start
# Autostart, falls die WSL-Instanz systemd hat (Standard bei neuen Installationen):
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files postgresql.service >/dev/null 2>&1; then
    sudo systemctl enable postgresql >/dev/null 2>&1 || true
else
    note "Kein systemd aktiv: nach jedem Windows-Neustart einmal 'sudo service postgresql start' ausfuehren."
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='vault'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE ROLE vault LOGIN PASSWORD 'vault';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='vault'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE vault OWNER vault;"

# --- 6. .env --------------------------------------------------------------------
step "[6/7] .env anlegen"
if [ ! -f .env ]; then
    cp .env.example .env
    # Prompt works both when run directly and when piped into bash (read from tty).
    API_KEY=""
    if [ -e /dev/tty ]; then
        printf 'Anthropic API Key (Enter = spaeter in .env eintragen): '
        IFS= read -r API_KEY < /dev/tty || API_KEY=""
    fi
    if [ -n "$API_KEY" ]; then
        sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$API_KEY|" .env
        echo "    API-Key eingetragen."
    else
        note "Kein Key eingetragen. Tests + Postgres-Demos laufen trotzdem (keyless);"
        note "fuer die LLM-Pipeline spaeter ANTHROPIC_API_KEY in $TARGET_DIR/.env setzen."
    fi
else
    echo "    .env existiert bereits - unveraendert gelassen."
fi

# --- 7. Keyless smoke test -------------------------------------------------------
step "[7/7] Smoke-Test (pytest, ohne API-Key)"
if uv run pytest -q; then
    SMOKE="Testsuite gruen."
else
    SMOKE="ACHTUNG: Testsuite nicht gruen - Ausgabe oben pruefen."
fi

# --- Done -----------------------------------------------------------------------
step "Fertig - $SMOKE"
cat <<EOF

Naechste Schritte (in diesem Ubuntu-Terminal):

  cd $TARGET_DIR

  # 1) Lauffaehige End-to-End-Demo, KEIN API-Key noetig:
  cd demo/bank_postgres
  uv run python build_vault_models.py
  DBT_PROFILES_DIR=. uv run dbt deps
  DBT_PROFILES_DIR=. uv run dbt build --full-refresh

  # 2) Volle LLM-Pipeline (API-Key in .env vorausgesetzt):
  cd $TARGET_DIR
  uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output

Doku: README.md, docs/demos/, demo/bank_postgres/README.md
EOF
