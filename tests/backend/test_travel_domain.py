from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from app.domain.travel import SearchRequest
from pydantic import ValidationError


def test_departure_date_uses_injected_clock_in_tehran() -> None:
    payload = {
        "mode": "flight",
        "origin": "THR",
        "destination": "MHD",
        "departure_date": "2026-09-16",
    }

    with pytest.raises(ValidationError, match="Departure date cannot be in the past"):
        SearchRequest.model_validate(
            payload,
            context={
                "clock": lambda: datetime(
                    2026,
                    9,
                    16,
                    21,
                    0,
                    tzinfo=timezone.utc,
                )
            },
        )


def test_departure_date_accepts_today_in_tehran() -> None:
    request = SearchRequest.model_validate(
        {
            "mode": "flight",
            "origin": "THR",
            "destination": "MHD",
            "departure_date": "2026-09-17",
        },
        context={
            "clock": lambda: datetime(
                2026,
                9,
                16,
                21,
                0,
                tzinfo=timezone.utc,
            )
        },
    )

    assert request.departure_date.isoformat() == "2026-09-17"


def test_round_trip_accepts_a_return_date_after_departure() -> None:
    request = SearchRequest(
        mode="flight",
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
        return_date=date(2030, 1, 20),
    )

    assert request.return_date == date(2030, 1, 20)


@pytest.mark.parametrize("return_day", (14, 15))
def test_round_trip_rejects_a_return_date_not_after_departure(
    return_day: int,
) -> None:
    with pytest.raises(ValidationError, match="Return date must be after departure"):
        SearchRequest(
            mode="flight",
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
            return_date=date(2030, 1, return_day),
        )
