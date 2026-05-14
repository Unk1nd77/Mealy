#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

has_frontend_script() {
  local script_name="$1"
  rg -q "\"${script_name}\"[[:space:]]*:" "${ROOT_DIR}/frontend/package.json"
}

run_backend() {
  echo "==> backend: format check"
  (
    cd "${ROOT_DIR}/backend"
    uv run ruff format --check .
  )

  echo "==> backend: lint"
  (
    cd "${ROOT_DIR}/backend"
    uv run ruff check .
  )

  echo "==> backend: tests"
  (
    cd "${ROOT_DIR}/backend"
    uv run pytest -q
  )
}

run_frontend() {
  if has_frontend_script "format:check"; then
    echo "==> frontend: format check"
    (
      cd "${ROOT_DIR}/frontend"
      npm run format:check
    )
  else
    echo "==> frontend: format check skipped (no format:check script)"
  fi

  if has_frontend_script "lint"; then
    echo "==> frontend: lint"
    (
      cd "${ROOT_DIR}/frontend"
      npm run lint
    )
  else
    echo "==> frontend: lint skipped (no lint script)"
  fi

  echo "==> frontend: build"
  (
    cd "${ROOT_DIR}/frontend"
    npm run build
  )
}

case "${1:-all}" in
  all)
    run_backend
    run_frontend
    ;;
  backend)
    run_backend
    ;;
  frontend)
    run_frontend
    ;;
  *)
    echo "usage: $0 [all|backend|frontend]" >&2
    exit 2
    ;;
esac
