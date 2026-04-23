"""Integration test. Requires both llama-servers running.

Run with:
    RF_INTEGRATION=1 uv run pytest tests/test_pipeline.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from src import config as cfg_mod
from src import pipeline, store


pytestmark = pytest.mark.skipif(
    os.environ.get("RF_INTEGRATION") != "1",
    reason="set RF_INTEGRATION=1 with llama-servers running",
)


def _make_fake_invoice(path: Path) -> None:
    img = Image.new("RGB", (1200, 1600), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "ACME Corp",
        "Invoice INV-001",
        "Date: 2026-04-20",
        "",
        "Widget           2   50.00   100.00",
        "Shipping                      23.45",
        "",
        "Total: 123.45",
    ]
    y = 80
    for line in lines:
        d.text((80, y), line, fill="black")
        y += 60
    img.save(path, "PNG")


def test_end_to_end(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "project"
    (root / "data" / "inbox").mkdir(parents=True)
    (root / "data" / "processed").mkdir(parents=True)
    (root / "data" / "failed").mkdir(parents=True)

    src_cfg = Path(__file__).resolve().parent.parent / "config.toml"
    shutil.copy(src_cfg, root / "config.toml")

    monkeypatch.setattr(cfg_mod, "ROOT", root)

    _make_fake_invoice(root / "data" / "inbox" / "sample.png")

    cfg = cfg_mod.load(root / "config.toml")
    counts = pipeline.ingest_folder(cfg)
    assert counts["ok"] + counts["partial"] >= 1

    conn = store.connect(cfg.paths.db)
    n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert n == 1
