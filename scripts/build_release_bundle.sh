#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${GENGSCOPE_RELEASE_VERSION:-0.1.0}"
DIST_DIR="$ROOT_DIR/dist"
ARCHIVE="$DIST_DIR/gengscope-${VERSION}-src.tar.gz"

mkdir -p "$DIST_DIR"
cd "$ROOT_DIR"

tar \
  --exclude='./dist' \
  --exclude='./.git' \
  --exclude='./.DS_Store' \
  --exclude='*/__pycache__' \
  --exclude='*/__pycache__/*' \
  --exclude='*/.pytest_cache' \
  --exclude='*/.pytest_cache/*' \
  --exclude='./services/api/.pytest_cache' \
  --exclude='./services/api/.uv-cache' \
  --exclude='./services/api/.venv' \
  --exclude='./services/api/.venv-system' \
  --exclude='./services/api/gengscope_api.egg-info' \
  --exclude='./services/api/gengscope_api.db' \
  --exclude='./services/api/data' \
  --exclude='./skills/codex' \
  --exclude='./backups' \
  -czf "$ARCHIVE" \
  README.md \
  docs \
  skills \
  services \
  infra \
  scripts \
  packages \
  apps \
  data/seeds \
  .github

printf '%s\n' "$ARCHIVE"
