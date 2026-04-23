from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    inbox: Path
    processed: Path
    failed: Path
    db: Path


@dataclass(frozen=True)
class OCRConfig:
    base_url: str
    model_name: str
    prompt: str
    max_image_edge: int
    timeout_seconds: int


@dataclass(frozen=True)
class StructureConfig:
    base_url: str
    model_name: str
    timeout_seconds: int
    max_retries: int


@dataclass(frozen=True)
class Config:
    paths: Paths
    ocr: OCRConfig
    structure: StructureConfig


def load(path: Path | None = None) -> Config:
    cfg_path = path or (ROOT / "config.toml")
    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)

    p = raw["paths"]
    paths = Paths(
        inbox=ROOT / p["inbox"],
        processed=ROOT / p["processed"],
        failed=ROOT / p["failed"],
        db=ROOT / p["db"],
    )
    ocr = OCRConfig(**raw["ocr"])
    structure = StructureConfig(**raw["structure"])
    return Config(paths=paths, ocr=ocr, structure=structure)
