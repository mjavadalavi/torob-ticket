from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.adapters.alibaba import (
    AlibabaBusAdapter,
    AlibabaFlightAdapter,
    AlibabaTrainAdapter,
)
from app.adapters.alibaba.http import AlibabaHttpClient
from app.adapters.booking import BookingFlightAdapter
from app.adapters.booking.http import BookingHttpClient
from app.adapters.flytoday import FlyTodayBusAdapter, FlyTodayFlightAdapter
from app.adapters.flytoday.http import FlyTodayHttpClient
from app.adapters.mrbilit import (
    MrBilitBusAdapter,
    MrBilitFlightAdapter,
    MrBilitTrainAdapter,
)
from app.adapters.mrbilit.http import MrBilitHttpClient
from app.adapters.payaneha import PayanehaBusAdapter
from app.adapters.payaneha.http import PayanehaHttpClient
from app.adapters.safar724 import Safar724BusAdapter
from app.adapters.safar724.http import Safar724HttpClient
from app.adapters.snapptrip import (
    SnappTripBusAdapter,
    SnappTripFlightAdapter,
    SnappTripTrainAdapter,
)
from app.adapters.snapptrip.http import SnappTripHttpClient
from app.ports.travel_adapter import AdapterFactory
from app.services.provider_support import validate_provider_support_registry


@dataclass(frozen=True, slots=True)
class LiveAdapterResources:
    """Provider transports owned by the application lifespan."""

    alibaba: AlibabaHttpClient
    booking: BookingHttpClient
    flytoday: FlyTodayHttpClient
    mrbilit: MrBilitHttpClient
    payaneha: PayanehaHttpClient
    safar724: Safar724HttpClient
    snapptrip: SnappTripHttpClient

    async def aclose(self) -> None:
        await asyncio.gather(
            self.alibaba.aclose(),
            self.booking.aclose(),
            self.flytoday.aclose(),
            self.mrbilit.aclose(),
            self.payaneha.aclose(),
            self.safar724.aclose(),
            self.snapptrip.aclose(),
        )


def register_live_adapters(
    factory: AdapterFactory,
    *,
    timeout_seconds: float = 5.0,
    offer_ttl_seconds: int = 900,
    max_entries: int = 5_000,
) -> LiveAdapterResources:
    """Register only integrations whose live contracts have been verified."""

    alibaba = AlibabaHttpClient(timeout_seconds=timeout_seconds)
    booking = BookingHttpClient(timeout_seconds=timeout_seconds)
    flytoday = FlyTodayHttpClient(timeout_seconds=timeout_seconds)
    mrbilit = MrBilitHttpClient(timeout_seconds=timeout_seconds)
    payaneha = PayanehaHttpClient(timeout_seconds=timeout_seconds)
    safar724 = Safar724HttpClient(timeout_seconds=timeout_seconds)
    snapptrip = SnappTripHttpClient(timeout_seconds=timeout_seconds)
    adapter_context = {
        "offer_ttl_seconds": offer_ttl_seconds,
        "max_entries": max_entries,
    }
    factory.register(
        AlibabaFlightAdapter(http_client=alibaba, **adapter_context)
    )
    factory.register(
        AlibabaTrainAdapter(http_client=alibaba, **adapter_context)
    )
    factory.register(
        AlibabaBusAdapter(http_client=alibaba, **adapter_context)
    )
    factory.register(
        BookingFlightAdapter(http_client=booking, **adapter_context)
    )
    factory.register(
        FlyTodayFlightAdapter(http_client=flytoday, **adapter_context)
    )
    factory.register(
        FlyTodayBusAdapter(http_client=flytoday, **adapter_context)
    )
    factory.register(
        SnappTripFlightAdapter(http_client=snapptrip, **adapter_context)
    )
    factory.register(
        SnappTripBusAdapter(http_client=snapptrip, **adapter_context)
    )
    factory.register(
        SnappTripTrainAdapter(http_client=snapptrip, **adapter_context)
    )
    factory.register(
        MrBilitFlightAdapter(http_client=mrbilit, **adapter_context)
    )
    factory.register(
        MrBilitTrainAdapter(http_client=mrbilit, **adapter_context)
    )
    factory.register(
        MrBilitBusAdapter(http_client=mrbilit, **adapter_context)
    )
    factory.register(
        PayanehaBusAdapter(http_client=payaneha, **adapter_context)
    )
    factory.register(
        Safar724BusAdapter(http_client=safar724, **adapter_context)
    )
    validate_provider_support_registry(factory)
    return LiveAdapterResources(
        alibaba=alibaba,
        booking=booking,
        flytoday=flytoday,
        mrbilit=mrbilit,
        payaneha=payaneha,
        safar724=safar724,
        snapptrip=snapptrip,
    )
