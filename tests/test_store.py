from __future__ import annotations

from pathlib import Path

from src import store
from src.structure import ExtractedDocument, LineItem


def _sample() -> ExtractedDocument:
    return ExtractedDocument(
        doc_type="invoice",
        language="en",
        fields={
            "vendor": "ACME Corp",
            "date": "2026-04-20",
            "total": 123.45,
            "invoice_number": "INV-001",
        },
        line_items=[
            LineItem(position=1, description="Widget", quantity=2, unit_price=50.00, amount=100.00),
            LineItem(position=2, description="Shipping", amount=23.45),
        ],
    )


def test_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = store.connect(db)

    doc_id = store.save(
        conn,
        source_path=Path("/tmp/fake.pdf"),
        sha256="abc123",
        page_count=1,
        raw_markdown="# hello",
        extracted=_sample(),
        raw_structured=None,
        model_ocr="test-ocr",
        model_struct="test-struct",
        status="ok",
    )
    assert doc_id > 0
    assert store.already_ingested(conn, "abc123")
    assert not store.already_ingested(conn, "other")

    rows = conn.execute("SELECT doc_type, status FROM documents").fetchall()
    assert rows == [("invoice", "ok")]

    fields = {k: (t, n, d) for k, t, n, d in conn.execute(
        "SELECT key, value_text, value_num, value_date FROM document_fields"
    ).fetchall()}
    assert fields["vendor"] == ("ACME Corp", None, None)
    assert fields["date"] == (None, None, "2026-04-20")
    assert fields["total"] == (None, 123.45, None)

    items = conn.execute("SELECT position, description, amount FROM line_items ORDER BY position").fetchall()
    assert items == [(1, "Widget", 100.0), (2, "Shipping", 23.45)]


def test_unique_sha(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = store.connect(db)

    store.save(
        conn,
        source_path=Path("/a"),
        sha256="same",
        page_count=1,
        raw_markdown="",
        extracted=None,
        raw_structured=None,
        model_ocr="m",
        model_struct="m",
        status="partial",
    )
    try:
        store.save(
            conn,
            source_path=Path("/b"),
            sha256="same",
            page_count=1,
            raw_markdown="",
            extracted=None,
            raw_structured=None,
            model_ocr="m",
            model_struct="m",
            status="partial",
        )
    except Exception:
        return
    raise AssertionError("expected uniqueness violation")
