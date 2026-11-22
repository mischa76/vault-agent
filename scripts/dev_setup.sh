#!/usr/bin/env bash
# Local dev setup. Run once after cloning.
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install from https://docs.astral.sh/uv/"
  exit 1
fi

uv sync --extra dev
cp -n .env.example .env || true
echo "Setup done. Edit .env to add your ANTHROPIC_API_KEY."
