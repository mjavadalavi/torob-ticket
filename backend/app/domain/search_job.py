from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.search import SearchResponse


class SearchJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SearchJobFailure:
    """Sanitized failure data safe to expose through the public API."""

    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class SearchJobRecord:
    """One short-lived background-search state transition record."""

    search_id: str
    status: SearchJobStatus
    created_at: datetime
    updated_at: datetime
    result: SearchResponse | None = None
    error: SearchJobFailure | None = None

