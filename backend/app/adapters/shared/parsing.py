from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.core.errors import AdapterUnavailableError

TEHRAN_TIMEZONE = timezone(timedelta(hours=3, minutes=30))


def number(value: Any) -> int | float | None:
    """Parse a finite-looking provider number across Persian/Arabic digits."""

    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    )
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", "").replace("٬", ""))
    if match is None:
        return None
    parsed = float(match.group())
    return int(parsed) if parsed.is_integer() else parsed


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-like provider timestamp and normalize it to Tehran time."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif value is None:
        return None
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TEHRAN_TIMEZONE)
    return parsed.astimezone(TEHRAN_TIMEZONE)


class ProviderRowError(ValueError):
    """A provider row cannot be mapped without guessing required fields."""


def mapping_rows_or_raise(
    rows: Sequence[object],
    *,
    invalid_message: str,
) -> list[Mapping[str, Any]]:
    """Keep object-shaped rows and reject wholly malformed non-empty lists.

    Provider endpoints occasionally return a syntactically valid JSON list
    with a changed item shape. Treating that payload as an empty result would
    falsely tell callers that no offers exist.
    """

    mapping_rows = [row for row in rows if isinstance(row, Mapping)]
    if rows and not mapping_rows:
        raise AdapterUnavailableError(invalid_message)
    return mapping_rows
