"""Desktop wrapper: spawns Streamlit and opens it in a native window via pywebview.

llama-server instances are NOT managed here. Start them separately with
`./scripts/start_models.sh` (or use the `.command` launcher which does both).
"""
from __future__ import annotations

import atexit
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import webview

_ROOT = Path(__file__).resolve().parent.parent
_STREAMLIT_PORT = int(os.environ.get("RF_STREAMLIT_PORT", "8501"))
_STREAMLIT_URL = f"http://127.0.0.1:{_STREAMLIT_PORT}"


def _start_streamlit() -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "STREAMLIT_SERVER_HEADLESS": "true",
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
            "STREAMLIT_SERVER_PORT": str(_STREAMLIT_PORT),
            "STREAMLIT_SERVER_ADDRESS": "127.0.0.1",
        }
    )
    log_path = _ROOT / "logs" / "streamlit.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(_ROOT / "src" / "dashboard.py"),
        ],
        cwd=str(_ROOT),
        env=env,
        stdout=log,
        stderr=log,
    )


def _wait_ready(url: str, timeout_s: float = 45.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=2.0).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def cli_desktop() -> int:
    proc = _start_streamlit()

    def _cleanup() -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    atexit.register(_cleanup)

    if not _wait_ready(f"{_STREAMLIT_URL}/_stcore/health"):
        _cleanup()
        print(
            f"Streamlit failed to start at {_STREAMLIT_URL}. "
            f"Check {_ROOT / 'logs' / 'streamlit.log'}",
            file=sys.stderr,
        )
        return 1

    webview.create_window(
        "revenueForecast",
        _STREAMLIT_URL,
        width=1400,
        height=900,
        min_size=(960, 640),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(cli_desktop())
