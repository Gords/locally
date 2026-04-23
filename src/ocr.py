from __future__ import annotations

import base64
from pathlib import Path

import httpx

from .config import OCRConfig


def _encode_image(path: Path) -> str:
    data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def extract_page(cfg: OCRConfig, image_path: Path) -> str:
    """Send one page to the OCR llama-server and return markdown."""
    url = cfg.base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _encode_image(image_path)}},
                    {"type": "text", "text": cfg.prompt},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }
    with httpx.Client(timeout=cfg.timeout_seconds) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]


def extract_document(cfg: OCRConfig, pages: list[Path]) -> str:
    chunks: list[str] = []
    for i, p in enumerate(pages, 1):
        md = extract_page(cfg, p)
        chunks.append(f"<!-- page {i} -->\n{md}")
    return "\n\n".join(chunks)
