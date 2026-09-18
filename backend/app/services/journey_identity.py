from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Protocol

from app.domain.offer import ProviderOffer
from app.domain.travel import TravelMode

_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_BUS_COMPANY_PREFIXES = re.compile(r"^(?:(?:شرکت|مسافربری|تعاونی)\s+)+")
_BUS_COOPERATIVE_NUMBER = re.compile(r"تعاونی(?:\s+شماره)?\s*(\d+)")
_PARENTHETICAL = re.compile(r"\s*[\(\[（].*?[\)\]）]\s*")
_FLIGHT_OPERATOR_PREFIXES = re.compile(r"^(?:شرکت\s+)?هواپیمایی\s+")
_FLIGHT_OPERATOR_SUFFIXES = re.compile(
    r"\s+(?:ایر|ایرلاین|air|airline|airlines|airways)$"
)
_STANDARD_TICKET_TYPES = frozenset(
    {"", "normal", "regular", "system", "سیستمی", "عادی", "معمولی"}
)
_BUS_COMPANY_ALIASES = (
    ("ترابربیتا", "ترابر بی تا"),
    ("لواننور", "لوان نور"),
    ("رویالسفرایرانیان", "رویال سفر"),
    ("رویالسفر", "رویال سفر"),
    ("ایمنسفر", "ایمن سفر"),
    ("سیروسفر", "سیر و سفر"),
    ("ایرانپیما", "ایران پیما"),
    ("پیکصبا", "پیک صبا"),
    ("میهننور", "میهن نور"),
    ("گیتیپیما", "گیتی پیما"),
    ("جوانسیرایثار", "جوان سیر ایثار"),
)
_BUS_COOPERATIVE_COMPANIES = {
    "6": "ایمن سفر",
    "8": "لوان نور",
    "15": "ترابر بی تا",
}


def canonical_text(value: str | None) -> str:
    """Normalize provider spelling differences without inventing aliases."""

    if value is None:
        return ""
    normalized = (
        unicodedata.normalize("NFKC", value)
        .translate(_DIGIT_TRANSLATION)
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .casefold()
    )
    return " ".join(normalized.split())


def canonical_departure(value: datetime) -> str:
    """Use one UTC minute for journey identity, independent of source timezone."""

    return value.astimezone(UTC).replace(second=0, microsecond=0).isoformat()


def canonical_arrival(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).replace(second=0, microsecond=0).isoformat()


class JourneyIdentityStrategy(Protocol):
    def components(self, offer: ProviderOffer) -> tuple[str, ...]: ...


class ScheduledServiceIdentity:
    """Identity for scheduled services whose product class is part of the offer."""

    def components(self, offer: ProviderOffer) -> tuple[str, ...]:
        ticket_type = canonical_text(offer.attributes.ticket_type)
        if ticket_type.replace("-", "").replace(" ", "") in _STANDARD_TICKET_TYPES:
            ticket_type = "standard"
        return (
            canonical_text(offer.origin),
            canonical_text(offer.destination),
            canonical_departure(offer.departure_at),
            canonical_text(offer.attributes.operator),
            canonical_text(offer.attributes.service_number),
            canonical_text(offer.attributes.vehicle_class),
            ticket_type,
        )


class FlightJourneyIdentity:
    """Conservative identity for the complete flight information we can verify.

    The shared model currently has one service number rather than every segment.
    Connected itineraries therefore include their opaque source identity so two
    different connections are never merged merely because their first segment
    looks alike. Direct flights can still be matched across providers.
    """

    @staticmethod
    def _operator(value: str) -> str:
        normalized = _FLIGHT_OPERATOR_PREFIXES.sub("", canonical_text(value))
        # OTAs sometimes append an alternate/former brand in parentheses, e.g.
        # «کارون (نفت)», while another source returns only «کارون». Route,
        # departure minute, flight number and cabin still guard identity.
        normalized = " ".join(_PARENTHETICAL.sub(" ", normalized).split())
        return _FLIGHT_OPERATOR_SUFFIXES.sub("", normalized).strip()

    @staticmethod
    def _cabin_family(value: str | None) -> str:
        compact = canonical_text(value).replace("-", "").replace(" ", "")
        families = (
            (("economy", "اکونومی", "اقتصادی"), "economy"),
            (("business", "بیزینس", "تجاری"), "business"),
            (("first", "فرست", "درجهیک"), "first"),
        )
        for aliases, family in families:
            if any(alias in compact for alias in aliases):
                return family
        return compact

    def components(self, offer: ProviderOffer) -> tuple[str, ...]:
        scheduled_flight = (
            canonical_text(offer.origin),
            canonical_text(offer.destination),
            canonical_departure(offer.departure_at),
            self._operator(offer.attributes.operator),
            canonical_text(offer.attributes.service_number),
            str(offer.attributes.stops) if offer.attributes.stops is not None else "",
        )
        if offer.attributes.stops not in (None, 0):
            return (
                *scheduled_flight,
                canonical_arrival(offer.arrival_at),
                self._cabin_family(offer.attributes.vehicle_class),
                f"connected:{offer.source_offer_id}",
            )
        # A direct scheduled flight remains one result card when OTAs disagree
        # on duration or expose economy/business and system/charter as separate
        # fares. Those distinctions stay visible in seller_offers.
        return scheduled_flight


class BusJourneyIdentity:
    """Same-minute identity based on fields shared reliably by live providers."""

    @staticmethod
    def _company(value: str) -> str:
        normalized = canonical_text(value)
        without_suffix = _PARENTHETICAL.sub(" ", normalized)
        cooperative = _BUS_COOPERATIVE_NUMBER.search(without_suffix)
        without_cooperative = _BUS_COOPERATIVE_NUMBER.sub(" ", without_suffix)
        cleaned = " ".join(_BUS_COMPANY_PREFIXES.sub("", without_cooperative).split())
        compact = re.sub(r"[^\w]+", "", cleaned, flags=re.UNICODE)
        for alias, canonical in _BUS_COMPANY_ALIASES:
            if alias in compact:
                return canonical
        if cooperative is not None:
            number = cooperative.group(1)
            return _BUS_COOPERATIVE_COMPANIES.get(number, f"cooperative:{number}")
        if cleaned:
            return cleaned
        return ""

    @staticmethod
    def _class_family(value: str | None) -> str:
        compact = canonical_text(value).replace("-", "").replace(" ", "")
        return "vip" if "vip" in compact or "ویآیپی" in compact else "normal"

    def components(self, offer: ProviderOffer) -> tuple[str, ...]:
        return (
            canonical_text(offer.origin),
            canonical_text(offer.destination),
            canonical_departure(offer.departure_at),
            self._company(offer.attributes.operator),
            self._class_family(offer.attributes.vehicle_class),
        )


DEFAULT_JOURNEY_IDENTITY_STRATEGIES: Mapping[
    TravelMode, JourneyIdentityStrategy
] = MappingProxyType(
    {
        TravelMode.FLIGHT: FlightJourneyIdentity(),
        TravelMode.TRAIN: ScheduledServiceIdentity(),
        TravelMode.BUS: BusJourneyIdentity(),
    }
)
