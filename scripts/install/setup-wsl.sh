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
    note "WARNING: target directory is under /mnt/* (Windows filesystem) - this is VERY slow."
    note "Recommended: leave VAULT_AGENT_DIR unset (default: ~/vault-agent on ext4)."
fi

# --- 1. System packages -------------------------------------------------------
step "[1/7] System packages (git, curl, PostgreSQL)"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl ca-certificates postgresql postgresql-contrib

# --- 2. uv ---------------------------------------------------------------------
step "[2/7] uv (Python toolchain)"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

# --- 3. Clone / update repo ----------------------------------------------------
step "[3/7] Repo -> $TARGET_DIR"
if [ -d "$TARGET_DIR/.git" ]; then
    git -C "$TARGET_DIR" pull --ff-only || note "git pull failed (local changes?) - continuing with the existing checkout."
else
    git clone "$REPO_URL" "$TARGET_DIR"
fi
cd "$TARGET_DIR"

# --- 4. Python environment -----------------------------------------------------
step "[4/7] Python environment (uv sync, incl. demo and dev extras)"
uv sync --extra demo --extra dev

# --- 5. PostgreSQL: service + role/db 'vault' ----------------------------------
step "[5/7] Starting PostgreSQL and creating role/db 'vault'"
sudo service postgresql start
# Autostart if this WSL instance has systemd (default on fresh installations):
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files postgresql.service >/dev/null 2>&1; then
    sudo systemctl enable postgresql >/dev/null 2>&1 || true
else
    note "No systemd active: after each Windows reboot, run 'sudo service postgresql start' once."
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='vault'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE ROLE vault LOGIN PASSWORD 'vault';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='vault'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE vault OWNER vault;"

# --- 6. .env --------------------------------------------------------------------
step "[6/7] Creating .env"
if [ ! -f .env ]; then
    cp .env.example .env
    # Prompt works both when run directly and when piped into bash (read from tty).
    API_KEY=""
    if [ -e /dev/tty ]; then
        printf 'Anthropic API key (Enter = add to .env later): '
        IFS= read -r API_KEY < /dev/tty || API_KEY=""
    fi
    if [ -n "$API_KEY" ]; then
        sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$API_KEY|" .env
        echo "    API key written."
    else
        note "No key entered. Tests + Postgres demos still work (keyless);"
        note "for the LLM pipeline, set ANTHROPIC_API_KEY in $TARGET_DIR/.env later."
    fi
else
    echo "    .env already exists - left unchanged."
fi

# --- 7. Keyless smoke test -------------------------------------------------------
step "[7/7] Smoke test (pytest, no API key)"
if uv run pytest -q; then
    SMOKE="Test suite green."
else
    SMOKE="WARNING: test suite not green - check the output above."
fi

# --- Done -----------------------------------------------------------------------
step "Done - $SMOKE"
cat <<EOF

Next steps (in this Ubuntu terminal):

  cd $TARGET_DIR

  # 1) Runnable end-to-end demo, NO API key needed:
  cd demo/bank_postgres
  uv run python build_vault_models.py
  DBT_PROFILES_DIR=. uv run dbt deps
  DBT_PROFILES_DIR=. uv run dbt build --full-refresh

  # 2) Full LLM pipeline (requires API key in .env):
  cd $TARGET_DIR
  uv run vault-agent run examples/inputs/health_insurance_requirements.md --out output

Docs: README.md, docs/demos/, demo/bank_postgres/README.md
EOF
