#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -q -r services/gateway/requirements.txt
python -m pytest -q tests/gateway
