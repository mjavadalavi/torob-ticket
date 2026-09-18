from __future__ import annotations

from typing import Literal

from app.domain.travel import ApiModel


class HealthResponse(ApiModel):
    status: Literal["ok"]
    environment: str
