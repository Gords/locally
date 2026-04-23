from __future__ import annotations

import io
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running via `streamlit run src/dashboard.py` where this file is __main__
# and relative imports would fail.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src import config as cfg_mod  # noqa: E402
from src import normalize, ocr, store, structure  # noqa: E402
from src.export import _fields_wide  # noqa: E402
from src.pipeline import process_one  # noqa: E402
from src.render import docs_to_markdown, doc_to_markdown  # noqa: E402


def _load(db_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    conn = sqlite3.connect(db_path)
    try:
        docs = pd.read_sql("SELECT * FROM documents", conn)
        fields = pd.read_sql("SELECT * FROM document_fields", conn)
        items = pd.read_sql("SELECT * FROM line_items", conn)
    finally:
        conn.close()
    return docs, fields, items


def _excel_bytes(df: pd.DataFrame, sheet: str = "data") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name=sheet, index=False)
    return buf.getvalue()


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 1
    while (target.parent / f"{stem}_{i}{suffix}").exists():
        i += 1
    return target.parent / f"{stem}_{i}{suffix}"


def _tab_upload(cfg: cfg_mod.Config) -> None:
    st.subheader("Drop documents")

    uploads = st.file_uploader(
        "PDFs or images",
        type=["pdf", "png", "jpg", "jpeg", "tiff", "tif", "webp", "bmp"],
        accept_multiple_files=True,
        key="uploader",
    )

    st.caption(
        f"Files are saved to `{cfg.paths.inbox.relative_to(_ROOT)}/`, "
        "processed via the OCR + structuring models, and moved to `processed/` on success."
    )

    if not uploads:
        st.info("Pick one or more files to begin.")
        return

    run = st.button(f"Process {len(uploads)} file(s)", type="primary")
    if not run:
        return

    cfg.paths.inbox.mkdir(parents=True, exist_ok=True)
    conn = store.connect(cfg.paths.db)
    new_doc_ids: list[int] = []
    skipped_doc_ids: list[int] = []
    results: list[dict] = []

    progress = st.progress(0.0, text="starting")
    status_area = st.empty()
    log_area = st.container()

    try:
        for i, up in enumerate(uploads, 1):
            target = _unique_path(cfg.paths.inbox / up.name)
            target.write_bytes(up.getbuffer())
            digest = normalize.sha256_file(target)

            status_area.write(f"Processing {target.name} ({i}/{len(uploads)})...")
            t0 = time.perf_counter()
            status = process_one(cfg, target, conn)
            elapsed = time.perf_counter() - t0

            row = conn.execute(
                "SELECT id FROM documents WHERE sha256 = ?", (digest,)
            ).fetchone()
            doc_id = row[0] if row else None

            if status in ("ok", "partial") and doc_id is not None:
                new_doc_ids.append(doc_id)
            elif status == "skipped" and doc_id is not None:
                skipped_doc_ids.append(doc_id)

            results.append(
                {"file": up.name, "status": status, "seconds": round(elapsed, 1)}
            )
            label = "already in database" if status == "skipped" else status
            log_area.write(f"- **{up.name}** → `{label}` in {elapsed:.1f}s")
            progress.progress(i / len(uploads), text=f"{i}/{len(uploads)} done")
    finally:
        conn.close()

    progress.empty()
    status_area.empty()

    ok = sum(1 for r in results if r["status"] == "ok")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("ok", ok)
    c2.metric("partial", partial)
    c3.metric("failed", failed)
    c4.metric("duplicate", skipped)

    if skipped_doc_ids and not new_doc_ids:
        st.info(
            f"All {skipped} file(s) were already processed earlier (matched by sha256). "
            "Showing the existing extraction below."
        )
    elif skipped_doc_ids:
        st.info(
            f"{skipped} file(s) were already in the database; showing their existing extraction alongside the new one(s)."
        )

    export_ids = new_doc_ids + skipped_doc_ids
    if not export_ids:
        st.warning("Nothing to export — all uploads failed.")
        return

    conn = sqlite3.connect(cfg.paths.db)
    try:
        markdown = docs_to_markdown(conn, export_ids)
    finally:
        conn.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"extracted_{ts}.md"

    st.download_button(
        "Download combined .md",
        data=markdown.encode("utf-8"),
        file_name=filename,
        mime="text/markdown",
        type="primary",
    )

    with st.expander("Preview", expanded=True):
        st.markdown(markdown)


def _tab_browse(cfg: cfg_mod.Config) -> None:
    if not cfg.paths.db.exists():
        st.info(f"no database yet at `{cfg.paths.db}` — upload some files first")
        return

    docs, fields, items = _load(cfg.paths.db)
    if docs.empty:
        st.info("database is empty — upload some files on the other tab")
        return

    wide = _fields_wide(fields)
    merged = docs.merge(wide, left_on="id", right_on="document_id", how="left") if not wide.empty else docs

    with st.sidebar:
        st.header("Filters")
        types = sorted([t for t in merged["doc_type"].dropna().unique()])
        picked = st.multiselect("doc_type", types, default=types)
        statuses = sorted(merged["status"].dropna().unique())
        picked_status = st.multiselect("status", statuses, default=statuses)

    view = merged[
        merged["doc_type"].isin(picked) & merged["status"].isin(picked_status)
    ].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("documents", len(view))
    c2.metric("ok", int((view["status"] == "ok").sum()))
    c3.metric("partial/failed", int(view["status"].isin(["partial", "failed"]).sum()))

    st.subheader("By doc type")
    type_counts = view.groupby("doc_type", dropna=False).size().reset_index(name="count")
    st.plotly_chart(px.bar(type_counts, x="doc_type", y="count"), use_container_width=True)

    if "total" in view.columns:
        totals = view.copy()
        totals["total_num"] = pd.to_numeric(totals["total"], errors="coerce")
        if totals["total_num"].notna().any():
            st.subheader("Totals over time")
            totals["ingested_at"] = pd.to_datetime(totals["ingested_at"], errors="coerce")
            st.plotly_chart(
                px.line(
                    totals.sort_values("ingested_at"),
                    x="ingested_at",
                    y="total_num",
                    color="doc_type",
                    markers=True,
                ),
                use_container_width=True,
            )

    st.subheader("Documents")
    st.dataframe(view, use_container_width=True)

    col_xlsx, col_md = st.columns(2)
    col_xlsx.download_button(
        "Export filtered to Excel",
        data=_excel_bytes(view),
        file_name="export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if not view.empty:
        conn = sqlite3.connect(cfg.paths.db)
        try:
            md_all = docs_to_markdown(conn, view["id"].tolist())
        finally:
            conn.close()
        col_md.download_button(
            "Export filtered to .md",
            data=md_all.encode("utf-8"),
            file_name="export.md",
            mime="text/markdown",
        )

    with st.expander("Line items"):
        st.dataframe(
            items[items["document_id"].isin(view["id"])],
            use_container_width=True,
        )

    st.subheader("Per-document markdown")
    if view.empty:
        return
    labels = {
        int(r["id"]): f"[{r['id']}] {Path(r['source_path']).name} ({r['status']})"
        for _, r in view.iterrows()
    }
    pick = st.selectbox("pick a document", options=list(labels.keys()), format_func=lambda k: labels[k])
    if pick is not None:
        conn = sqlite3.connect(cfg.paths.db)
        try:
            md_one = doc_to_markdown(conn, int(pick))
        finally:
            conn.close()
        st.download_button(
            "Download this document as .md",
            data=md_one.encode("utf-8"),
            file_name=f"doc_{pick}.md",
            mime="text/markdown",
        )
        st.markdown(md_one)


def main() -> None:
    st.set_page_config(page_title="revenueForecast", layout="wide")
    st.title("revenueForecast")

    cfg = cfg_mod.load()

    tab_upload, tab_browse = st.tabs(["Upload & Extract", "Browse"])
    with tab_upload:
        _tab_upload(cfg)
    with tab_browse:
        _tab_browse(cfg)


def cli_dashboard() -> int:
    script = Path(__file__).resolve()
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(script)])


if __name__ == "__main__":
    main()
