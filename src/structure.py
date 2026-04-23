from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from .config import StructureConfig


DocType = Literal["invoice", "receipt", "statement", "letter", "form", "other"]


class LineItem(BaseModel):
    position: int | None = None
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class ExtractedDocument(BaseModel):
    doc_type: DocType
    language: str = "unknown"
    fields: dict[str, str | float | int | None] = Field(default_factory=dict)
    line_items: list[LineItem] = Field(default_factory=list)
    notes: str | None = None


SYSTEM_PROMPT = """You extract structured data from OCR'd documents.
Return STRICT JSON matching the schema exactly. Do not include commentary.

CRITICAL STRUCTURE — these keys are at the TOP LEVEL, NOT nested inside "fields":
  doc_type, language, fields, line_items, notes

"fields" is a FLAT dict of scalar key/value pairs ONLY (strings/numbers/dates).
"line_items" is a TOP-LEVEL array (siblings of "fields"), never inside it.

EXAMPLE of correct shape (illustrative only — DO NOT copy these values, use ONLY what is in the document):
{
  "doc_type": "invoice",
  "language": "en",
  "fields": {
    "vendor": "<example vendor name>",
    "invoice_number": "<example invoice id>",
    "date": "2099-12-31",
    "subtotal": 1.11,
    "tax": 2.22,
    "total": 3.33,
    "currency": "XYZ"
  },
  "line_items": [
    {"position": 1, "description": "<item from doc>", "quantity": 0, "unit_price": 0.0, "amount": 0.0}
  ],
  "notes": null
}

Rules:
- Put key/value scalars (vendor, date, total, subtotal, tax, currency, invoice_number, customer, etc.) into "fields". Use keys appropriate to the doc_type.
- Put itemized rows into the TOP-LEVEL "line_items" array. Only include rows that are actual line items, NOT totals/subtotals/tax rows.
- Numbers must be numeric (no currency symbols or commas). Dates as YYYY-MM-DD strings.
- If unknown, omit the key (do not invent values). Use the date PRINTED on the document; do not guess the current year.
- For invoices/receipts/statements: ALWAYS include "total" in fields if the document shows one, plus "subtotal" and "tax" when present. Also include "currency".
- For line items, carry the amount into "amount" even when quantity/unit_price are missing (e.g., "Shipping $23.45" → amount: 23.45).
"""


def _schema_hint() -> str:
    return json.dumps(ExtractedDocument.model_json_schema(), indent=2)


def _request(cfg: StructureConfig, markdown: str, error_feedback: str | None = None) -> str:
    url = cfg.base_url.rstrip("/") + "/v1/chat/completions"
    user = f"JSON schema:\n{_schema_hint()}\n\nDocument (markdown):\n{markdown}"
    if error_feedback:
        user += f"\n\nYour previous response failed validation: {error_feedback}\nReturn corrected JSON only."

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=cfg.timeout_seconds) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[: -3]
    return s.strip()


def parse(cfg: StructureConfig, markdown: str) -> tuple[ExtractedDocument | None, str | None]:
    """Return (extracted, raw_json). `extracted` is None if validation failed after retries."""
    last_err: str | None = None
    raw: str | None = None
    for attempt in range(cfg.max_retries + 1):
        raw = _request(cfg, markdown, error_feedback=last_err)
        try:
            data = json.loads(_strip_fences(raw))
            return ExtractedDocument.model_validate(data), raw
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = str(e)[:500]
    return None, raw
