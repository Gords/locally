#!/usr/bin/env bash
# Launch both llama-server instances. Logs go to ./data/.
# Stop with ./scripts/stop_models.sh

set -euo pipefail

cd "$(dirname "$0")/.."

OCR_MODEL="${OCR_MODEL:-ggml-org/GLM-OCR-GGUF:Q8_0}"
STRUCT_MODEL="${STRUCT_MODEL:-unsloth/Qwen3.5-4B-GGUF:Q4_K_M}"

OCR_PORT="${OCR_PORT:-8080}"
STRUCT_PORT="${STRUCT_PORT:-8081}"

mkdir -p data logs
PID_DIR="data"
LOG_DIR="logs"

if ! command -v llama-server >/dev/null 2>&1; then
    echo "llama-server not found. Install with: brew install llama.cpp" >&2
    exit 1
fi

_already_running() {
    local pidfile="$1"
    [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

OFFLINE_FLAG="${RF_ONLINE:+}"
if [[ -z "$OFFLINE_FLAG" ]]; then OFFLINE_FLAG="--offline"; fi

start() {
    local name="$1" model="$2" port="$3" extra="${4:-}"
    local pidfile="$PID_DIR/$name.pid"
    local logfile="$LOG_DIR/$name.log"
    if _already_running "$pidfile"; then
        echo "$name already running (pid $(cat "$pidfile"))"
        return
    fi
    echo "starting $name on :$port ($model) $OFFLINE_FLAG"
    # shellcheck disable=SC2086
    nohup llama-server -hf "$model" --port "$port" --host 127.0.0.1 \
        --n-gpu-layers 999 $OFFLINE_FLAG $extra > "$logfile" 2>&1 &
    echo $! > "$pidfile"
    echo "  pid $(cat "$pidfile") log $logfile"
}

start ocr    "$OCR_MODEL"    "$OCR_PORT"    "--ctx-size 8192"
start struct "$STRUCT_MODEL" "$STRUCT_PORT" "--ctx-size 32768"

echo ""
echo "health:"
echo "  curl http://127.0.0.1:$OCR_PORT/health"
echo "  curl http://127.0.0.1:$STRUCT_PORT/health"
