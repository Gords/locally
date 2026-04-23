from __future__ import annotations

import argparse
import shutil
import sys
import traceback
from pathlib import Path

from . import config as cfg_mod
from . import normalize, ocr, store, structure


def _move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / src.name
    if target.exists():
        stem, suffix = src.stem, src.suffix
        i = 1
        while (dst_dir / f"{stem}_{i}{suffix}").exists():
            i += 1
        target = dst_dir / f"{stem}_{i}{suffix}"
    shutil.move(str(src), target)
    return target


def process_one(cfg: cfg_mod.Config, src: Path, conn) -> str:
    """Process one file. Returns status string: 'ok' | 'partial' | 'failed' | 'skipped'."""
    digest = normalize.sha256_file(src)
    if store.already_ingested(conn, digest):
        _move(src, cfg.paths.processed)
        return "skipped"

    pages_dir = normalize.temp_pages_dir()
    try:
        pages = normalize.to_pages(src, pages_dir, max_edge=cfg.ocr.max_image_edge)
        markdown = ocr.extract_document(cfg.ocr, pages)
        extracted, raw = structure.parse(cfg.structure, markdown)
        status = "ok" if extracted else "partial"

        store.save(
            conn,
            source_path=src,
            sha256=digest,
            page_count=len(pages),
            raw_markdown=markdown,
            extracted=extracted,
            raw_structured=raw,
            model_ocr=cfg.ocr.model_name,
            model_struct=cfg.structure.model_name,
            status=status,
        )
        _move(src, cfg.paths.processed)
        return status
    except Exception:
        traceback.print_exc()
        try:
            _move(src, cfg.paths.failed)
        except Exception:
            pass
        return "failed"
    finally:
        shutil.rmtree(pages_dir, ignore_errors=True)


def ingest_folder(cfg: cfg_mod.Config) -> dict[str, int]:
    conn = store.connect(cfg.paths.db)
    counts = {"ok": 0, "partial": 0, "failed": 0, "skipped": 0}
    try:
        files = [
            p
            for p in sorted(cfg.paths.inbox.iterdir())
            if p.is_file() and p.suffix.lower() in normalize.SUPPORTED
        ]
        if not files:
            print(f"no files in {cfg.paths.inbox}")
            return counts
        for f in files:
            print(f"-> {f.name}", flush=True)
            status = process_one(cfg, f, conn)
            counts[status] += 1
            print(f"   {status}", flush=True)
    finally:
        conn.close()
    print(f"done: {counts}")
    return counts


def cli_ingest() -> int:
    parser = argparse.ArgumentParser(description="Ingest documents from inbox into SQLite")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()
    cfg = cfg_mod.load(args.config)
    counts = ingest_folder(cfg)
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(cli_ingest())
