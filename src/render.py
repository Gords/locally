from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def _fmt_value(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, float) and v.is_integer():
        return f"{v:.2f}"
    return str(v)


def doc_to_markdown(conn: sqlite3.Connection, doc_id: int) -> str:
    """Render one document row as a human-readable markdown block."""
    doc = conn.execute(
        """SELECT source_path, doc_type, ingested_at, page_count, status,
                  model_ocr, model_struct, raw_markdown
             FROM documents WHERE id = ?""",
        (doc_id,),
    ).fetchone()
    if doc is None:
        return f"# document {doc_id} not found\n"

    source_path, doc_type, ingested_at, pages, status, m_ocr, m_struct, raw_md = doc
    name = Path(source_path).name

    fields = conn.execute(
        "SELECT key, value_text, value_num, value_date FROM document_fields WHERE document_id = ? ORDER BY key",
        (doc_id,),
    ).fetchall()

    items = conn.execute(
        """SELECT position, description, quantity, unit_price, amount
             FROM line_items WHERE document_id = ? ORDER BY position""",
        (doc_id,),
    ).fetchall()

    parts: list[str] = []
    parts.append(f"# {name}")
    parts.append("")
    parts.append(f"- **Type**: {doc_type or 'unknown'}")
    parts.append(f"- **Status**: {status}")
    parts.append(f"- **Pages**: {pages}")
    parts.append(f"- **Ingested**: {ingested_at}")
    parts.append(f"- **Models**: ocr=`{m_ocr}` · struct=`{m_struct}`")
    parts.append("")

    if fields:
        parts.append("## Fields")
        parts.append("")
        parts.append("| Key | Value |")
        parts.append("| --- | --- |")
        for key, vt, vn, vd in fields:
            val = vd if vd is not None else (_fmt_value(vn) if vn is not None else (vt or ""))
            parts.append(f"| {key} | {val} |")
        parts.append("")

    if items:
        parts.append("## Line items")
        parts.append("")
        parts.append("| # | Description | Qty | Unit | Amount |")
        parts.append("| --- | --- | --- | --- | --- |")
        for pos, desc, qty, unit, amt in items:
            parts.append(
                f"| {pos or ''} | {desc or ''} | {_fmt_value(qty)} | {_fmt_value(unit)} | {_fmt_value(amt)} |"
            )
        parts.append("")

    if raw_md:
        parts.append("## Raw OCR")
        parts.append("")
        parts.append("```")
        parts.append(raw_md.strip())
        parts.append("```")
        parts.append("")

    return "\n".join(parts)


def docs_to_markdown(conn: sqlite3.Connection, doc_ids: list[int]) -> str:
    blocks = [doc_to_markdown(conn, i) for i in doc_ids]
    sep = "\n\n---\n\n"
    header = f"<!-- revenueForecast export: {len(doc_ids)} document(s) -->\n\n"
    return header + sep.join(blocks)
