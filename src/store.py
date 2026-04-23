from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .structure import ExtractedDocument


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY,
    source_path   TEXT NOT NULL,
    sha256        TEXT UNIQUE NOT NULL,
    doc_type      TEXT,
    ingested_at   TEXT NOT NULL DEFAULT (datetime('now')),
    page_count    INTEGER,
    raw_markdown  TEXT,
    structured    TEXT,
    model_ocr     TEXT,
    model_struct  TEXT,
    status        TEXT CHECK(status IN ('ok','partial','failed'))
);

CREATE TABLE IF NOT EXISTS document_fields (
    id           INTEGER PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    key          TEXT NOT NULL,
    value_text   TEXT,
    value_num    REAL,
    value_date   TEXT
);
CREATE INDEX IF NOT EXISTS idx_fields_key ON document_fields(key);
CREATE INDEX IF NOT EXISTS idx_fields_doc ON document_fields(document_id);

CREATE TABLE IF NOT EXISTS line_items (
    id           INTEGER PRIMARY KEY,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    position     INTEGER,
    description  TEXT,
    quantity     REAL,
    unit_price   REAL,
    amount       REAL,
    raw          TEXT
);
"""

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def already_ingested(conn: sqlite3.Connection, sha256: str) -> bool:
    row = conn.execute("SELECT 1 FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
    return row is not None


def _classify_value(v: str | float | int | None) -> tuple[str | None, float | None, str | None]:
    if v is None:
        return (None, None, None)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (None, float(v), None)
    s = str(v).strip()
    if ISO_DATE.match(s):
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return (None, None, s)
        except ValueError:
            pass
    return (s, None, None)


def save(
    conn: sqlite3.Connection,
    *,
    source_path: Path,
    sha256: str,
    page_count: int,
    raw_markdown: str,
    extracted: ExtractedDocument | None,
    raw_structured: str | None,
    model_ocr: str,
    model_struct: str,
    status: str,
) -> int:
    structured_json = raw_structured if extracted is None else extracted.model_dump_json()
    doc_type = extracted.doc_type if extracted else None

    cur = conn.execute(
        """
        INSERT INTO documents
            (source_path, sha256, doc_type, page_count, raw_markdown,
             structured, model_ocr, model_struct, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(source_path),
            sha256,
            doc_type,
            page_count,
            raw_markdown,
            structured_json,
            model_ocr,
            model_struct,
            status,
        ),
    )
    doc_id = cur.lastrowid

    if extracted:
        field_rows = []
        for k, v in extracted.fields.items():
            t, n, d = _classify_value(v)
            field_rows.append((doc_id, k, t, n, d))
        if field_rows:
            conn.executemany(
                "INSERT INTO document_fields (document_id, key, value_text, value_num, value_date) VALUES (?, ?, ?, ?, ?)",
                field_rows,
            )

        item_rows = [
            (
                doc_id,
                li.position,
                li.description,
                li.quantity,
                li.unit_price,
                li.amount,
                json.dumps(li.model_dump(), default=str),
            )
            for li in extracted.line_items
        ]
        if item_rows:
            conn.executemany(
                "INSERT INTO line_items (document_id, position, description, quantity, unit_price, amount, raw) VALUES (?, ?, ?, ?, ?, ?, ?)",
                item_rows,
            )

    conn.commit()
    return doc_id
