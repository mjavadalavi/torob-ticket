from __future__ import annotations

from app.domain.offer import Seller

SNAPPTRIP_FLIGHT_SEARCH_URL = (
    "https://flight.snapptrip.com/dom-flights/v1/one-way/search"
)
SNAPPTRIP_FLIGHT_LOCATIONS_URL = (
    "https://store.snapptrip.com/assets/json/dom-flight-search-suggestions.json"
)
SNAPPTRIP_BUS_AVAILABILITY_URL = (
    "https://bus.snapptrip.com/bus-listing-go/v2/availability"
)
SNAPPTRIP_BUS_LOCATIONS_URL = (
    "https://fp.snapptrip.com/bus-listing-go/v3/endpoints"
)
SNAPPTRIP_TRAIN_STATIONS_URL = "https://train.snapptrip.com/statics/v1/stations"
SNAPPTRIP_TRAIN_SEARCH_URL = "https://train.snapptrip.com/listing/v2/search"
SNAPPTRIP_SELLER = Seller(
    id="snapptrip",
    name="اسنپ‌تریپ",
    rating=None,
    review_count=None,
    logo_url=(
        "https://store.snapptrip.com/assets/builds/website/"
        "_next/static/media/logo.12xjc4xr19yoa.png"
    ),
)


# These aliases are the only non-provider identifiers translated locally. Their
# targets were observed in SnappTrip's endpoint search response and result URL.
SNAPPTRIP_BUS_ALIASES = {
    "THR": "تهران",
    "MHD": "مشهد",
    "IFN": "اصفهان",
    "RHD": "رشت",
    "TBZ": "تبریز",
    "AZD": "یزد",
    "SYZ": "شیراز",
    "AWZ": "اهواز",
    "KER": "کرمان",
}


# Canonical public location codes are translated only to station names that are
# present in SnappTrip's live stations document. The listing API itself accepts
# the station's `nameEn`, which is resolved dynamically by the adapter.
SNAPPTRIP_TRAIN_ALIASES = {
    "THR": "تهران",
    "MHD": "مشهد",
    "IFN": "اصفهان",
    "RHD": "رشت",
    "TBZ": "تبریز",
    "AZD": "یزد",
    "SYZ": "شیراز",
    "AWZ": "اهواز",
    "KER": "کرمان",
}
