#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

stop() {
    local name="$1"
    local pidfile="data/$name.pid"
    if [[ ! -f "$pidfile" ]]; then
        echo "$name: no pidfile"
        return
    fi
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
        echo "stopping $name (pid $pid)"
        kill "$pid" || true
        sleep 0.5
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" || true
    else
        echo "$name: pid $pid not running"
    fi
    rm -f "$pidfile"
}

stop ocr
stop struct
