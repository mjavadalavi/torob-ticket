from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode, urljoin

from app.adapters.mrbilit.base import MrBilitOfferStore
from app.adapters.mrbilit.http import MrBilitHttpClient
from app.adapters.mrbilit.parsing import (
    TEHRAN_TIMEZONE,
    bounded_text,
    normalized_text,
    number,
    parse_datetime,
)
from app.adapters.mrbilit.spec import (
    MRBILIT_SELLER,
    MRBILIT_TRAIN_SEARCH_URL,
    MRBILIT_TRAIN_STATIONS,
    MrBilitTrainStation,
)
from app.adapters.shared.branding import (
    MRBILIT_LOGO_HOSTS,
    train_operator_logo_url,
    trusted_logo_url,
)
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.itinerary import OfferAttributes, TrainDetails
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import SearchRequest, TrainSearchPreferences, TravelMode
from app.ports.capabilities import SupportsRefundRules
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)

_GENDER_CODES = {"male": 1, "female": 2, "family": 3}


class MrBilitTrainAdapter(
    MrBilitOfferStore,
    TravelAdapter,
    SupportsRefundRules,
    SupportsLocationSearch,
):
    """Verified MrBilit domestic-train web API integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: MrBilitHttpClient | None = None,
    ) -> None:
        MrBilitOfferStore.__init__(
            self,
            offer_ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._http = http_client or MrBilitHttpClient(
            timeout_seconds=timeout_seconds
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.TRAIN

    @property
    def provider(self) -> str:
        return "mrbilit"

    @property
    def seller(self) -> Seller:
        return MRBILIT_SELLER

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        needle = normalized_text(query)
        matching = [
            station
            for station in MRBILIT_TRAIN_STATIONS
            if not needle
            or needle
            in normalized_text(
                " ".join(
                    (
                        station.name,
                        station.slug,
                        str(station.id),
                        *station.aliases,
                    )
                )
            )
        ]
        matching.sort(
            key=lambda station: (
                normalized_text(station.name) != needle,
                not normalized_text(station.name).startswith(needle),
                station.name,
            )
        )
        return tuple(
            TravelLocation(
                code=station.slug,
                name=station.name,
                mode=self.mode,
                kind=LocationKind.RAILWAY_STATION,
                providers=[self.provider],
            )
            for station in matching[: max(1, limit)]
        )

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("MrBilitTrainAdapter only accepts train searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "قطار رفت‌وبرگشت مستربلیط باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, TrainSearchPreferences)
            else TrainSearchPreferences(mode=TravelMode.TRAIN)
        )
        if preferences.vehicle_transport:
            raise AdapterUnavailableError(
                "حمل خودرو در قرارداد زندهٔ مستربلیط برای مقایسهٔ قیمت "
                "تأیید نشده است."
            )
        origin = self._resolve_station(request.origin)
        destination = self._resolve_station(request.destination)
        if origin.id == destination.id:
            raise AdapterUnavailableError("مبدأ و مقصد قطار نمی‌توانند یکسان باشند.")
        gender_code = _GENDER_CODES[preferences.passenger_type]
        query = {
            "from": origin.id,
            "to": destination.id,
            "date": f"{request.departure_date.isoformat()}T00:00:00.000Z",
            "genderCode": gender_code,
            "adultCount": request.passengers.adults,
            "childCount": request.passengers.children,
            "infantCount": request.passengers.infants,
            "disableCache": False,
            "exclusive": preferences.exclusive_compartment,
            "availableStatus": "Both",
        }
        try:
            rows, content_path = await self._fetch_rows(query)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("MrBilit train search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات قطار از مستربلیط وجود ندارد."
            ) from exc

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
            try:
                parsed = self._parse_offers(
                    row,
                    request=request,
                    preferences=preferences,
                    origin=origin,
                    destination=destination,
                    gender_code=gender_code,
                    content_path=content_path,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed MrBilit train row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            for offer in parsed:
                self._remember_offer(
                    offer,
                    self._redirect_url(
                        request=request,
                        preferences=preferences,
                        origin_slug=origin.slug,
                        destination_slug=destination.slug,
                        gender_code=gender_code,
                    ),
                )
                offers.append(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج قطار مستربلیط نامعتبر بود."
            )
        return tuple(offers)

    @staticmethod
    def _resolve_station(value: str) -> MrBilitTrainStation:
        needle = normalized_text(value)
        matches = [
            station
            for station in MRBILIT_TRAIN_STATIONS
            if needle
            in {
                normalized_text(station.name),
                normalized_text(station.slug),
                normalized_text(str(station.id)),
                *(normalized_text(alias) for alias in station.aliases),
            }
        ]
        if len(matches) != 1:
            raise AdapterUnavailableError(
                "شناسهٔ ایستگاه این مسیر در فهرست تأییدشدهٔ مستربلیط نیست."
            )
        return matches[0]

    async def _fetch_rows(
        self,
        query: Mapping[str, Any],
    ) -> tuple[list[Mapping[str, Any]], str]:
        response = await self._http.request_json(
            MRBILIT_TRAIN_SEARCH_URL,
            query=query,
        )
        rows = response.get("trains") if isinstance(response, Mapping) else None
        content_path = (
            bounded_text(response.get("contentPath"), maximum=300)
            if isinstance(response, Mapping)
            else ""
        )
        if not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ جست‌وجوی قطار مستربلیط معتبر نبود.")
        return (
            mapping_rows_or_raise(
                rows,
                invalid_message="ساختار نتایج قطار مستربلیط نامعتبر بود.",
            ),
            content_path,
        )

    def _parse_offers(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: TrainSearchPreferences,
        origin: MrBilitTrainStation,
        destination: MrBilitTrainStation,
        gender_code: int,
        content_path: str,
    ) -> list[ProviderOffer]:
        train_id = bounded_text(row.get("id"), maximum=100)
        train_number = bounded_text(row.get("trainNumber"), maximum=20)
        departure = parse_datetime(row.get("departureTime"))
        arrival = parse_datetime(row.get("arrivalTime"))
        provider_origin = number(row.get("from"))
        provider_destination = number(row.get("to"))
        company = bounded_text(
            row.get("corporationName") or row.get("providerName"), maximum=100
        )
        company_code = bounded_text(
            row.get("corporationID") or row.get("provider"), maximum=40
        ) or None
        if (
            not train_id
            or not train_number
            or departure is None
            or arrival is None
            or arrival <= departure
            or departure.date() != request.departure_date
            or provider_origin != origin.id
            or provider_destination != destination.id
            or not company
        ):
            raise ProviderRowError("required train fields are missing or invalid")

        prices = row.get("prices")
        if not isinstance(prices, list):
            raise ProviderRowError("train prices are missing")
        offers: list[ProviderOffer] = []
        for price_group in prices:
            if not isinstance(price_group, Mapping):
                continue
            if number(price_group.get("sellType")) != gender_code:
                continue
            classes = price_group.get("classes")
            if not isinstance(classes, list):
                continue
            for price_class in classes:
                if not isinstance(price_class, Mapping):
                    continue
                offer = self._parse_price_class(
                    price_class,
                    row=row,
                    request=request,
                    preferences=preferences,
                    origin=origin,
                    destination=destination,
                    departure=departure,
                    arrival=arrival,
                    train_id=train_id,
                    train_number=train_number,
                    company=company,
                    company_code=company_code,
                    content_path=content_path,
                )
                if offer is not None:
                    offers.append(offer)
        return offers

    def _parse_price_class(
        self,
        price_class: Mapping[str, Any],
        *,
        row: Mapping[str, Any],
        request: SearchRequest,
        preferences: TrainSearchPreferences,
        origin: MrBilitTrainStation,
        destination: MrBilitTrainStation,
        departure: datetime,
        arrival: datetime,
        train_id: str,
        train_number: str,
        company: str,
        company_code: str | None,
        content_path: str,
    ) -> ProviderOffer | None:
        class_id = bounded_text(price_class.get("id"), maximum=100)
        price_rials = number(price_class.get("price"))
        discount_rials = number(price_class.get("discount")) or 0
        capacity = number(price_class.get("capacity"))
        minimum_people = number(price_class.get("minPersons")) or 1
        wagon_name = bounded_text(price_class.get("wagonName"), maximum=80)
        if (
            not class_id
            or price_rials is None
            or price_rials <= 0
            or discount_rials < 0
            or discount_rials > price_rials
            or capacity is None
            or not float(capacity).is_integer()
            or capacity < 0
            or not wagon_name
            or minimum_people < 1
        ):
            raise ProviderRowError("train price class is invalid")
        if (
            price_class.get("isAvailable") is not True
            or price_class.get("reservationAvailable") is not True
            or capacity < request.passengers.total
            or minimum_people > request.passengers.total
        ):
            return None

        operator = bounded_text(
            price_class.get("ownerName"), maximum=100
        ) or company
        operator_code = bounded_text(
            price_class.get("owner"), maximum=40
        ) or company_code
        compartment = number(price_class.get("compartmentCapacity"))
        compartment_capacity = None
        if compartment is not None:
            if (
                not float(compartment).is_integer()
                or compartment < 1
                or compartment > 12
            ):
                raise ProviderRowError("train compartment capacity is invalid")
            compartment_capacity = round(compartment)

        logo = train_operator_logo_url(company) or self._logo_url(
            content_path,
            bounded_text(price_class.get("svgLogoPath"), maximum=200),
        ) or train_operator_logo_url(company)
        cancellation = bounded_text(
            price_class.get("cancellationTerms"), maximum=240
        ) or None
        cancellable = row.get("cancellable")
        refundable = cancellable if isinstance(cancellable, bool) else None
        if refundable is False and not cancellation:
            cancellation = "این بلیت غیرقابل‌استرداد است."
        capabilities = (
            [Capability.REFUND_RULES]
            if refundable is not None and cancellation
            else []
        )

        return ProviderOffer(
            source_offer_id=f"{train_id}:{class_id}",
            origin=origin.name,
            destination=destination.name,
            departure_at=departure,
            arrival_at=arrival,
            price=Money(
                amount=round(
                    ((price_rials - discount_rials) * request.passengers.total)
                    / 10
                )
            ),
            attributes=OfferAttributes(
                operator=operator,
                operator_code=operator_code,
                operator_logo_url=logo,
                service_number=train_number,
                vehicle_class=wagon_name,
                ticket_type="system",
                stops=0,
            ),
            mode_details=TrainDetails(
                mode=TravelMode.TRAIN,
                railway_company=operator,
                train_number=train_number,
                class_name=wagon_name,
                compartment_capacity=compartment_capacity,
                private_compartment_available=(
                    True if preferences.exclusive_compartment else None
                ),
                women_only_available=(
                    True if preferences.passenger_type == "female" else None
                ),
                vehicle_transport_available=None,
            ),
            capabilities=capabilities,
            remaining_seats=round(capacity),
            cancellation_summary=cancellation,
            refundable=refundable,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _logo_url(content_path: str, relative_path: str):
        if not content_path or not relative_path or "default" in relative_path.casefold():
            return None
        return trusted_logo_url(
            urljoin(content_path.rstrip("/") + "/", relative_path),
            allowed_hosts=MRBILIT_LOGO_HOSTS,
        )

    @staticmethod
    def _redirect_url(
        *,
        request: SearchRequest,
        preferences: TrainSearchPreferences,
        origin_slug: str,
        destination_slug: str,
        gender_code: int,
    ) -> str:
        query_items: dict[str, Any] = {
            "departureDate": request.departure_date.isoformat(),
            "adultCount": request.passengers.adults,
            "childCount": request.passengers.children,
            "infantCount": request.passengers.infants,
        }
        if gender_code != 3:
            query_items["sellTypeCode"] = gender_code
        if preferences.exclusive_compartment:
            query_items["exclusive"] = 1
        return (
            "https://mrbilit.com/trains/"
            f"{quote(origin_slug, safe='')}-{quote(destination_slug, safe='')}?"
            f"{urlencode(query_items)}"
        )
