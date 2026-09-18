"""Compatibility re-exports for callers migrating to split domain modules."""

from app.domain.capabilities import (
    Capability,
    RefundRules,
    Seat,
    SeatMap,
    VehicleTransport,
    merge_capabilities,
)
from app.domain.itinerary import (
    BusDetails,
    FlightDetails,
    OfferAttributes,
    TrainDetails,
    TravelDetails,
)
from app.domain.offer import (
    Currency,
    Money,
    NormalizedOffer,
    OfferDetails,
    OfferGroup,
    ProviderOffer,
    RecommendationReason,
    Seller,
)
from app.domain.travel import (
    ApiModel,
    BusSearchPreferences,
    FlightSearchPreferences,
    PassengerCounts,
    SearchIntent,
    SearchRequest,
    TrainSearchPreferences,
    TravelMode,
    TravelSearchPreferences,
)

__all__ = [
    "ApiModel",
    "BusDetails",
    "BusSearchPreferences",
    "Capability",
    "Currency",
    "FlightDetails",
    "FlightSearchPreferences",
    "Money",
    "NormalizedOffer",
    "OfferAttributes",
    "OfferDetails",
    "OfferGroup",
    "PassengerCounts",
    "ProviderOffer",
    "RecommendationReason",
    "RefundRules",
    "SearchIntent",
    "SearchRequest",
    "Seat",
    "SeatMap",
    "Seller",
    "TrainDetails",
    "TrainSearchPreferences",
    "TravelDetails",
    "TravelMode",
    "TravelSearchPreferences",
    "VehicleTransport",
    "merge_capabilities",
]
