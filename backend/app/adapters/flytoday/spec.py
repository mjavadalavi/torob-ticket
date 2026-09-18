from __future__ import annotations

from app.domain.offer import Seller

FLYTODAY_FLIGHT_LOCATION_URL = (
    "https://www.flytodayir.com/api/gateway/flight/search"
)
FLYTODAY_FLIGHT_SEARCH_URL = (
    "https://www.flytodayir.com/api/gateway/V1/flight/search"
)
FLYTODAY_BUS_LOCATION_URL = "https://placesearch.flytoday.ir/api/Bus/Search"
FLYTODAY_BUS_SEARCH_URL = (
    "https://www.flytodayir.com/api/gateway/V1/Bus/Search"
)

FLYTODAY_SELLER = Seller(
    id="flytoday",
    name="فلای‌تودی",
    rating=None,
    review_count=None,
    logo_url=(
        "https://cdn-a.cdnfl2.ir/upload/flytoday/public/white-labels/"
        "flytodayircom/images/logo.svg"
    ),
)
