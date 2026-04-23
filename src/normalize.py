from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".bmp"}
PDF_EXTS = {".pdf"}
SUPPORTED = IMAGE_EXTS | PDF_EXTS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resize(img: Image.Image, max_edge: int) -> Image.Image:
    w, h = img.size
    m = max(w, h)
    if m <= max_edge:
        return img
    scale = max_edge / m
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def to_pages(src: Path, out_dir: Path, max_edge: int = 2048) -> list[Path]:
    """Split a source file into per-page PNGs normalized for OCR.

    PDFs are rasterized at 200 DPI. Images are loaded, converted to RGB,
    optionally downscaled, and re-saved as PNG.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()
    pages: list[Path] = []

    if suffix in PDF_EXTS:
        pdf = pdfium.PdfDocument(str(src))
        for i, page in enumerate(pdf):
            pil = page.render(scale=200 / 72).to_pil().convert("RGB")
            pil = _resize(pil, max_edge)
            out = out_dir / f"{src.stem}_p{i+1:04d}.png"
            pil.save(out, "PNG")
            pages.append(out)
        pdf.close()
    elif suffix in IMAGE_EXTS:
        pil = Image.open(src).convert("RGB")
        pil = _resize(pil, max_edge)
        out = out_dir / f"{src.stem}_p0001.png"
        pil.save(out, "PNG")
        pages.append(out)
    else:
        raise ValueError(f"unsupported file type: {suffix}")

    return pages


def temp_pages_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="rf_pages_"))
