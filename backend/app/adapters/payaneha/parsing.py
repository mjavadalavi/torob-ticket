from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, ClassVar

from app.adapters.shared.parsing import TEHRAN_TIMEZONE, number

__all__ = [
    "TEHRAN_TIMEZONE",
    "PayanehaResultParser",
    "bounded_text",
    "normalized_text",
    "number",
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


class PayanehaResultParser(HTMLParser):
    """Extract only fields rendered in verified Payaneha result wrappers."""

    _VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
    _CLASS_FIELDS: ClassVar[dict[str, str]] = {
        "co-brand": "company_short",
        "co-name": "company",
        "bus-type": "bus_type",
        "date-move": "date",
        "time-move": "time",
        "capacity": "capacity",
        "price-pay": "price",
        "travel-route": "route",
        "more-info": "description",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._row: dict[str, str] | None = None
        self._stack: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if "result_wrapper" in classes:
            self._finish_row()
            self._row = {}
        if self._row is None:
            return
        if tag == "input" and attributes.get("name") == "GetID":
            value = bounded_text(attributes.get("value"), maximum=20_000)
            if value:
                self._row["id"] = value
        elif tag == "img":
            src = bounded_text(attributes.get("src"), maximum=500)
            if src:
                self._row.setdefault("logo", src)
        elif tag == "a" and "/busticket/terminal/" in (attributes.get("href") or ""):
            self._stack.append((tag, "origin_terminal"))
            return
        marker = next((field for name, field in self._CLASS_FIELDS.items() if name in classes), None)
        self._stack.append((tag, marker))
        if tag in self._VOID_TAGS:
            self._stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._row is None:
            return
        value = " ".join(data.split())
        if not value:
            return
        for _tag, marker in self._stack:
            if marker:
                self._row[marker] = f"{self._row.get(marker, '')} {value}".strip()

    def close(self) -> None:
        super().close()
        self._finish_row()

    def _finish_row(self) -> None:
        if self._row is not None:
            self.rows.append({key: bounded_text(value, maximum=20_000) for key, value in self._row.items() if value})
        self._row = None
        self._stack.clear()


def parse_price(value: Any) -> int | float | None:
    return number(value)


def parse_clock(value: Any) -> tuple[int, int] | None:
    match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", bounded_text(value, maximum=40))
    if match is None:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return (hour, minute) if hour <= 23 and minute <= 59 else None
