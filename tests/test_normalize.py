from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from src import normalize


def _make_png(path: Path, size: tuple[int, int] = (800, 600)) -> None:
    Image.new("RGB", size, color=(255, 255, 255)).save(path, "PNG")


def _make_pdf(path: Path, pages: int = 2) -> None:
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(612, 792)
    pdf.save(path)


def test_sha256_stable(tmp_path: Path) -> None:
    p = tmp_path / "a.png"
    _make_png(p)
    assert normalize.sha256_file(p) == normalize.sha256_file(p)


def test_png_passthrough(tmp_path: Path) -> None:
    src = tmp_path / "img.png"
    _make_png(src, (3000, 2000))
    out_dir = tmp_path / "pages"
    pages = normalize.to_pages(src, out_dir, max_edge=2048)
    assert len(pages) == 1
    with Image.open(pages[0]) as im:
        assert max(im.size) <= 2048


def test_pdf_split(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    _make_pdf(src, pages=3)
    out_dir = tmp_path / "pages"
    pages = normalize.to_pages(src, out_dir)
    assert len(pages) == 3
    for p in pages:
        assert p.suffix == ".png"


def test_unsupported_raises(tmp_path: Path) -> None:
    src = tmp_path / "x.txt"
    src.write_text("hi")
    try:
        normalize.to_pages(src, tmp_path / "pages")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
