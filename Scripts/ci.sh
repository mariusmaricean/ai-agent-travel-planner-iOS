#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${PYTHON_BIN:-}" && -x "$ROOT_DIR/Backend/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/Backend/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$ROOT_DIR/Backend"
"$PYTHON_BIN" -m unittest discover -s tests

cd "$ROOT_DIR"
xcodebuild \
  -project TravelPlanner.xcodeproj \
  -scheme TravelPlanner \
  -derivedDataPath "$ROOT_DIR/.build/DerivedData" \
  -destination 'generic/platform=iOS' \
  CODE_SIGNING_ALLOWED=NO \
  build
