#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Load .env if present (development convenience — POSIX-safe)
if [ -f ../.env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    export "$line"
  done < ../.env
fi

# On Railway, deps are installed at build time by nixpacks.
# In local dev (no nixpacks), install them here if needed.
if [ "${RAILWAY_ENVIRONMENT:-}" = "" ] && [ -f requirements.txt ]; then
  pip install -q --break-system-packages -r requirements.txt 2>/dev/null || true
fi

# Validate environment variables before launching
python3 validate_env.py

exec python3 bot.py
