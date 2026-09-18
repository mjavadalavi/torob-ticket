from __future__ import annotations

from typing import Any

from app.adapters.shared.parsing import TEHRAN_TIMEZONE, number, parse_datetime

__all__ = [
    "TEHRAN_TIMEZONE",
    "bounded_text",
    "normalized_text",
    "number",
    "parse_datetime",
]


def bounded_text(value: Any, *, maximum: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


def normalized_text(value: Any) -> str:
    return (
        " ".join(str(value or "").split())
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", "")
        .casefold()
    )
