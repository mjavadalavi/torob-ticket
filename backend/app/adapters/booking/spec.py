from __future__ import annotations

from app.domain.offer import Seller

BOOKING_FLIGHT_AIRPORTS_URL = "https://ws.booking.ir/nagaapi/api/v4/flight/airports/"
BOOKING_FLIGHT_SEARCH_URL = "https://ws.booking.ir/nagaapi/api/v4/flight/search/"
BOOKING_LOGO_HOSTS = frozenset({"www.booking.ir", "booking.ir"})

BOOKING_SELLER = Seller(
    id="booking",
    name="بوکینگ",
    rating=None,
    review_count=None,
    logo_url="https://www.booking.ir/images/logo.svg",
)
