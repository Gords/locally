from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from . import config as cfg_mod


def _read_documents(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT id, source_path, sha256, doc_type, ingested_at, page_count, status, model_ocr, model_struct FROM documents",
        conn,
    )


def _read_fields(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT document_id, key, value_text, value_num, value_date FROM document_fields",
        conn,
    )


def _read_line_items(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT document_id, position, description, quantity, unit_price, amount FROM line_items",
        conn,
    )


def _fields_wide(fields: pd.DataFrame) -> pd.DataFrame:
    if fields.empty:
        return pd.DataFrame()
    fields = fields.copy()
    fields["value"] = fields["value_text"].combine_first(
        fields["value_num"].astype("object")
    ).combine_first(fields["value_date"])
    return fields.pivot_table(
        index="document_id", columns="key", values="value", aggfunc="first"
    ).reset_index()


def to_excel(db_path: Path, out_path: Path) -> Path:
    conn = sqlite3.connect(db_path)
    try:
        docs = _read_documents(conn)
        fields = _read_fields(conn)
        items = _read_line_items(conn)
    finally:
        conn.close()

    wide = _fields_wide(fields)
    if not wide.empty:
        merged = docs.merge(wide, left_on="id", right_on="document_id", how="left")
        merged = merged.drop(columns=["document_id"], errors="ignore")
    else:
        merged = docs

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as xl:
        merged.to_excel(xl, sheet_name="all_documents", index=False)
        for dt, group in merged.groupby("doc_type", dropna=False):
            name = (dt or "unknown")[:31]
            group.to_excel(xl, sheet_name=name, index=False)
        items.to_excel(xl, sheet_name="line_items", index=False)
        fields.to_excel(xl, sheet_name="fields_long", index=False)

    return out_path


def cli_export() -> int:
    parser = argparse.ArgumentParser(description="Export SQLite to Excel workbook")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="output xlsx path")
    args = parser.parse_args()
    cfg = cfg_mod.load(args.config)
    out = args.out or cfg.paths.db.parent / "export.xlsx"
    written = to_excel(cfg.paths.db, out)
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(cli_export())
