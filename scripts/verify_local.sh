#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
API_DIR="$ROOT_DIR/services/api"

cd "$API_DIR"

if [[ -x ".venv-system/bin/python" ]]; then
  PYTEST_PY=".venv-system/bin/python"
elif [[ -x ".venv/bin/python" ]]; then
  PYTEST_PY=".venv/bin/python"
else
  PYTEST_PY="$PYTHON_BIN"
fi

"$PYTEST_PY" -m pytest -q

cd "$ROOT_DIR"
bash -n scripts/*.sh
python3 -m py_compile scripts/run_skill_case_demo.py
python3 -m py_compile scripts/run_retraction_calibration.py
python3 scripts/validate_skill.py skills/gengscope
docker compose -f infra/docker/docker-compose.yml config >/dev/null
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.demo.yml config >/dev/null

if [[ "${GENGSCOPE_VERIFY_DOCKER_BUILD:-0}" == "1" ]]; then
  docker compose -f infra/docker/docker-compose.yml build api worker
fi

printf 'GengScope local verification passed.\n'
