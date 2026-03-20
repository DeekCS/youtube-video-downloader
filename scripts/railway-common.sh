#!/usr/bin/env bash
# Shared helpers for Railway CLI scripts (source this file).
# shellcheck shell=bash

_RAILWAY_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Sets BACKEND_SLUG and FRONTEND_SLUG (exported) from RAILWAY_* env or `railway status --json`.
railway_load_service_slugs() {
  local be="${RAILWAY_BACKEND_SERVICE:-}"
  local fe="${RAILWAY_FRONTEND_SERVICE:-}"
  if [[ -n "$be" && -n "$fe" ]]; then
    BACKEND_SLUG="$be"
    FRONTEND_SLUG="$fe"
    export BACKEND_SLUG FRONTEND_SLUG
    return 0
  fi
  mapfile -t _rns < <(
    command -v railway >/dev/null 2>&1 &&
      railway status --json 2>/dev/null | python3 "$_RAILWAY_SCRIPTS_DIR/railway_resolve_service_names.py" 2>/dev/null ||
      true
  )
  BACKEND_SLUG="${be:-${_rns[0]:-Backend}}"
  FRONTEND_SLUG="${fe:-${_rns[1]:-Frontend}}"
  export BACKEND_SLUG FRONTEND_SLUG
}
