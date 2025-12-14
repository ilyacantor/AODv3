#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PIP_CONFIG_FILE="$PROJECT_ROOT/pip.conf"
export NO_PROXY="localhost,127.0.0.1,::1,package-proxy.replit.com"
export no_proxy="$NO_PROXY"

# Prefer uv for speed, fall back to pip if uv is unavailable.
if command -v uv >/dev/null 2>&1; then
  uv pip install --system --requirement "$PROJECT_ROOT/requirements.txt" --index-url https://package-proxy.replit.com/pypi/simple --trusted-host package-proxy.replit.com
else
  pip install --requirement "$PROJECT_ROOT/requirements.txt" --index-url https://package-proxy.replit.com/pypi/simple --trusted-host package-proxy.replit.com
fi
