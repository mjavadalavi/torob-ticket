from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.search_job import SearchJobStatus
from app.domain.travel import ApiModel
from app.schemas.search import SearchResponse


class SearchJobError(ApiModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    message: str = Field(min_length=1, max_length=160)
    retryable: bool


class SearchJobAccepted(ApiModel):
    search_id: str = Field(min_length=8, max_length=80)
    status: Literal[SearchJobStatus.QUEUED]


class SearchJobStatusResponse(ApiModel):
    search_id: str = Field(min_length=8, max_length=80)
    status: SearchJobStatus
    result: SearchResponse | None
    error: SearchJobError | None

    @model_validator(mode="after")
    def validate_state_payload(self) -> Self:
        if self.status is SearchJobStatus.COMPLETED:
            if self.result is None or self.error is not None:
                raise ValueError("Completed search jobs require only a result.")
        elif self.status is SearchJobStatus.FAILED:
            if self.error is None or self.result is not None:
                raise ValueError("Failed search jobs require only an error.")
        elif self.result is not None or self.error is not None:
            raise ValueError("Pending search jobs cannot include a result or error.")
        return self
