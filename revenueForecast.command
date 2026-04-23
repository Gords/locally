#!/usr/bin/env bash
# Double-click launcher for revenueForecast.
# Starts llama-server models (OCR + Qwen), opens the desktop app window.
# Shuts models down on exit.

set -e
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    osascript -e 'display alert "uv not found" message "Install uv: https://docs.astral.sh/uv/"'
    exit 1
fi

./scripts/start_models.sh

trap './scripts/stop_models.sh >/dev/null 2>&1 || true' EXIT

exec uv run rf-desktop
